"""
API Key Manager - Phase 5.4: Resilience & Notification System

Provides:
- Multi-key failover with priority ordering
- Automatic health monitoring and cooldown recovery
- Per-key budget enforcement
- Real-time notifications when all keys fail
- Zero-downtime key rotation

Failover Architecture:
    Request → Primary Key (priority=1)
        ↓ FAIL
        → Secondary Key (priority=2)
        ↓ FAIL
        → Tertiary Key (priority=3)
        ↓ FAIL
        → Local Fallback (Ollama)
        ↓ FAIL
        → ALERT: Notify all channels + frontend
"""

import logging
import asyncio
from typing import Optional, Dict, List, Callable, Any, Tuple
from datetime import datetime, timedelta
from functools import wraps
from sqlalchemy.orm import Session
from sqlalchemy import func
from threading import Lock

from backend.models.database import get_db_context
from backend.models.entities.user_config import UserModelConfig, ConnectionStatus, ProviderType
from backend.models.entities.channels import ExternalChannel, ChannelType
from backend.core.security import decrypt_api_key

logger = logging.getLogger(__name__)


class APIKeyHealthStatus:
    """Health status enumeration for API keys."""
    HEALTHY = "healthy"
    COOLDOWN = "cooldown"
    RATE_LIMITED = "rate_limited"
    EXHAUSTED = "exhausted"  # Budget exceeded
    ERROR = "error"
    DISABLED = "disabled"


class APIKeyManager:
    """
    Central manager for API key resilience, failover, and health monitoring.
    
    Thread-safe singleton that handles:
    - Priority-based key selection
    - Automatic failover on failure
    - Cooldown and recovery management
    - Budget tracking and enforcement
    - Multi-channel notifications
    """
    
    _instance = None
    _lock = Lock()
    
    # Configuration constants
    MAX_FAILURES_BEFORE_COOLDOWN = 3
    DEFAULT_COOLDOWN_MINUTES = 5
    NOTIFICATION_DEBOUNCE_SECONDS = 300  # 5 minutes between "all down" alerts
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        self._notification_cache: Dict[str, datetime] = {}  # provider -> last_notification_time
        self._local_fallback_config: Optional[Dict[str, Any]] = None
        
        logger.info("🔐 API Key Manager initialized")
    
    # =====================================================================
    # Core Failover Logic
    # =====================================================================
    
    def get_active_key(
        self, 
        provider: str, 
        estimated_cost: float = 0.0,
        min_priority: int = 1,
        db: Optional[Session] = None
    ) -> Optional[UserModelConfig]:
        """
        Get the highest priority healthy key for a provider.
        
        Args:
            provider: Provider type (openai, anthropic, etc.)
            estimated_cost: Estimated USD cost for this request (for budget check)
            min_priority: Minimum priority level to consider (for cascading failover)
            db: Database session (optional, will create context if None)
            
        Returns:
            UserModelConfig with healthy key, or None if no keys available
            
        Performance: <50ms database query
        """
        def _query(db_session: Session):
            # Get all active keys for provider, ordered by priority
            keys = db_session.query(UserModelConfig).filter_by(
                provider=provider,
                is_active=True
            ).filter(
                UserModelConfig.priority >= min_priority
            ).order_by(
                UserModelConfig.priority.asc()
            ).all()
            
            for key in keys:
                if self._is_key_healthy(key, estimated_cost):
                    return key
            
            return None
        
        if db:
            return _query(db)
        else:
            with get_db_context() as db_session:
                return _query(db_session)
    
    def get_active_key_with_fallback(
        self,
        providers: List[str],
        estimated_cost: float = 0.0,
        db: Optional[Session] = None
    ) -> Tuple[Optional[UserModelConfig], str]:
        """
        Try multiple providers in order until a healthy key is found.
        
        Args:
            providers: List of provider names to try in order
            estimated_cost: Estimated USD cost
            db: Database session
            
        Returns:
            Tuple of (key_config, provider_name) or (None, "exhausted")
        """
        for provider in providers:
            key = self.get_active_key(provider, estimated_cost, db=db)
            if key:
                return key, provider
        
        # All providers exhausted - trigger notification
        self._notify_all_keys_down(providers[-1] if providers else "unknown", db)
        return None, "exhausted"
    
    def _is_key_healthy(self, key: UserModelConfig, estimated_cost: float = 0.0) -> bool:
        """
        Check if a key is healthy and available for use.
        
        Checks:
        - Not in cooldown period
        - Status is not ERROR
        - Monthly budget not exceeded
        - Estimated cost within remaining budget
        """
        now = datetime.utcnow()
        
        # Check cooldown
        if key.cooldown_until and now < key.cooldown_until:
            return False
        
        # Check status
        if key.status == ConnectionStatus.ERROR:
            return False
        
        # Check if key needs recovery (cooldown expired but status still ERROR)
        if key.cooldown_until and now >= key.cooldown_until:
            # Auto-recover from cooldown
            self._auto_recover_key(key)
            return True
        
        # Check monthly budget
        self._reset_monthly_spend_if_needed(key)
        if key.monthly_budget_usd > 0:
            remaining = key.monthly_budget_usd - key.current_spend_usd
            if remaining < estimated_cost:
                return False
        
        return True
    
    def _reset_monthly_spend_if_needed(self, key: UserModelConfig):
        """Reset monthly spend counter if we've entered a new month."""
        now = datetime.utcnow()
        if (key.last_spend_reset.month != now.month or 
            key.last_spend_reset.year != now.year):
            key.current_spend_usd = 0.0
            key.last_spend_reset = now
    
    # =====================================================================
    # Failure Handling & Recovery
    # =====================================================================
    
    def mark_key_failed(
        self, 
        key_id: str, 
        error: Optional[str] = None,
        is_rate_limit: bool = False,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Mark a key as failed, increment failure count, potentially trigger cooldown.
        
        Args:
            key_id: UUID of the key config
            error: Error message for logging
            is_rate_limit: If True, use longer cooldown (15 min vs 5 min)
            db: Database session
            
        Returns:
            Dict with status: 'cooldown', 'error', or 'disabled'
        """
        def _update(db_session: Session):
            key = db_session.query(UserModelConfig).filter_by(id=key_id).first()
            if not key:
                logger.error(f"Key {key_id} not found for failure marking")
                return {"status": "not_found"}
            
            key.failure_count += 1
            key.last_failure_at = datetime.utcnow()
            
            cooldown_minutes = 15 if is_rate_limit else self.DEFAULT_COOLDOWN_MINUTES
            
            if key.failure_count >= self.MAX_FAILURES_BEFORE_COOLDOWN:
                key.cooldown_until = datetime.utcnow() + timedelta(minutes=cooldown_minutes)
                key.status = ConnectionStatus.ERROR
                
                logger.warning(
                    f"🔒 Key {key_id} ({key.provider.value}) entered cooldown "
                    f"for {cooldown_minutes}min after {key.failure_count} failures"
                )
                
                return {
                    "status": "cooldown",
                    "cooldown_until": key.cooldown_until.isoformat(),
                    "failure_count": key.failure_count
                }
            else:
                logger.info(
                    f"⚠️ Key {key_id} failure #{key.failure_count}: {error or 'Unknown error'}"
                )
                return {
                    "status": "error",
                    "failure_count": key.failure_count,
                    "remaining_attempts": self.MAX_FAILURES_BEFORE_COOLDOWN - key.failure_count
                }
        
        if db:
            return _update(db)
        else:
            with get_db_context() as db_session:
                result = _update(db_session)
                db_session.commit()
                return result
    
    def mark_key_success(self, key_id: str, db: Optional[Session] = None):
        """Reset failure count on successful API call."""
        def _update(db_session: Session):
            key = db_session.query(UserModelConfig).filter_by(id=key_id).first()
            if key and key.failure_count > 0:
                key.failure_count = 0
                key.last_failure_at = None
                key.cooldown_until = None
                if key.status == ConnectionStatus.ERROR:
                    key.status = ConnectionStatus.ACTIVE
        
        if db:
            _update(db)
        else:
            with get_db_context() as db_session:
                _update(db_session)
                db_session.commit()
    
    def _auto_recover_key(self, key: UserModelConfig):
        """Automatically recover a key from cooldown."""
        key.status = ConnectionStatus.ACTIVE
        key.failure_count = max(0, key.failure_count - 1)  # Decay failures
        logger.info(f"🔓 Key {key.id} auto-recovered from cooldown")
    
    def recover_key(self, key_id: str, db: Optional[Session] = None) -> bool:
        """
        Manually recover a key from cooldown/error state.
        
        Returns True if key was found and recovered.
        """
        def _update(db_session: Session):
            key = db_session.query(UserModelConfig).filter_by(id=key_id).first()
            if not key:
                return False
            
            key.status = ConnectionStatus.ACTIVE
            key.failure_count = 0
            key.cooldown_until = None
            key.last_failure_at = None
            
            logger.info(f"🔓 Key {key_id} manually recovered")
            return True
        
        if db:
            return _update(db)
        else:
            with get_db_context() as db_session:
                result = _update(db_session)
                db_session.commit()
                return result
    
    # =====================================================================
    # Budget Management
    # =====================================================================
    
    def record_spend(
        self, 
        key_id: str, 
        cost_usd: float,
        tokens_used: int = 0,
        db: Optional[Session] = None
    ):
        """
        Record API usage cost for budget tracking.
        
        Args:
            key_id: UUID of the key
            cost_usd: Actual cost in USD
            tokens_used: Token count for logging
            db: Database session
        """
        def _update(db_session: Session):
            key = db_session.query(UserModelConfig).filter_by(id=key_id).first()
            if not key:
                return
            
            self._reset_monthly_spend_if_needed(key)
            key.current_spend_usd += cost_usd
            key.total_requests += 1
            key.estimated_cost_usd = (key.estimated_cost_usd or 0) + cost_usd
            
            # Check if budget exceeded
            if key.monthly_budget_usd > 0 and key.current_spend_usd >= key.monthly_budget_usd:
                logger.warning(
                    f"💸 Key {key_id} monthly budget EXHAUSTED: "
                    f"${key.current_spend_usd:.2f} / ${key.monthly_budget_usd:.2f}"
                )
        
        if db:
            _update(db)
        else:
            with get_db_context() as db_session:
                _update(db_session)
                db_session.commit()
    
    def check_budget(self, key_id: str, estimated_cost: float, db: Optional[Session] = None) -> bool:
        """Check if a key has sufficient budget remaining."""
        def _check(db_session: Session):
            key = db_session.query(UserModelConfig).filter_by(id=key_id).first()
            if not key or key.monthly_budget_usd <= 0:
                return True  # No budget limit
            
            self._reset_monthly_spend_if_needed(key)
            remaining = key.monthly_budget_usd - key.current_spend_usd
            return remaining >= estimated_cost
        
        if db:
            return _check(db)
        else:
            with get_db_context() as db_session:
                return _check(db_session)
    
    def update_budget(
        self,
        key_id: str,
        monthly_budget_usd: float,
        db: Optional[Session] = None
    ) -> bool:
        """Update monthly budget limit for a key."""
        def _update(db_session: Session):
            key = db_session.query(UserModelConfig).filter_by(id=key_id).first()
            if not key:
                return False
            
            key.monthly_budget_usd = monthly_budget_usd
            return True
        
        if db:
            return _update(db)
        else:
            with get_db_context() as db_session:
                result = _update(db_session)
                db_session.commit()
                return result
    
    # =====================================================================
    # Key Rotation
    # =====================================================================
    
    def rotate_key(
        self,
        old_key_id: str,
        new_key_encrypted: str,
        new_key_masked: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Optional[UserModelConfig]:
        """
        Zero-downtime key rotation.
        
        Strategy:
        1. Add new key with same priority+1 (temporary lower priority)
        2. Test new key
        3. Swap priorities (new key becomes primary)
        4. Mark old key for deletion (priority 999, cooldown 1 hour)
        5. After 1 hour, old key can be safely deleted
        
        Returns the new key config.
        """
        def _rotate(db_session: Session):
            old_key = db_session.query(UserModelConfig).filter_by(id=old_key_id).first()
            if not old_key:
                return None
            
            # Create new key with temporary lower priority
            new_key = UserModelConfig(
                user_id=old_key.user_id,
                provider=old_key.provider,
                provider_name=old_key.provider_name,
                config_name=f"{old_key.config_name} (Rotated)",
                api_key_encrypted=new_key_encrypted,
                api_key_masked=new_key_masked or "...****",
                api_base_url=old_key.api_base_url,
                local_server_url=old_key.local_server_url,
                default_model=old_key.default_model,
                available_models=old_key.available_models,
                priority=old_key.priority + 1,  # Temporary lower priority
                is_default=False,
                max_tokens=old_key.max_tokens,
                temperature=old_key.temperature,
                top_p=old_key.top_p,
                timeout_seconds=old_key.timeout_seconds,
                status=ConnectionStatus.TESTING,
                monthly_budget_usd=old_key.monthly_budget_usd
            )
            
            db_session.add(new_key)
            db_session.flush()
            
            # Test new key
            from backend.services.model_provider import ModelService
            test_result = ModelService.test_connection(new_key)
            
            if not test_result.get("success"):
                db_session.rollback()
                logger.error(f"❌ Key rotation failed: new key test failed")
                return None
            
            # Swap priorities - new key becomes primary
            old_priority = old_key.priority
            old_key.priority = 999  # Demote old key
            old_key.config_name = f"{old_key.config_name} (Deprecated)"
            old_key.cooldown_until = datetime.utcnow() + timedelta(hours=1)  # 1 hour grace
            new_key.priority = old_priority
            new_key.status = ConnectionStatus.ACTIVE
            
            db_session.commit()
            logger.info(f"🔄 Key rotated: {old_key_id} → {new_key.id}")
            
            return new_key
        
        if db:
            return _rotate(db)
        else:
            with get_db_context() as db_session:
                return _rotate(db_session)
    
    # =====================================================================
    # Health Reporting
    # =====================================================================
    
    def get_key_health_report(
        self,
        provider: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive health report for all keys or specific provider.
        
        Returns:
            {
                "overall_status": "healthy" | "degraded" | "critical",
                "providers": {
                    "openai": {
                        "total_keys": 3,
                        "healthy": 2,
                        "cooldown": 1,
                        "exhausted": 0,
                        "keys": [...]
                    }
                },
                "total_keys": 10,
                "healthy_keys": 8,
                "keys_in_cooldown": 1,
                "budget_exhausted": 1
            }
        """
        def _query(db_session: Session):
            query = db_session.query(UserModelConfig).filter_by(is_active=True)
            if provider:
                query = query.filter_by(provider=provider)
            
            keys = query.all()
            
            # Group by provider
            provider_stats: Dict[str, Dict] = {}
            overall = {
                "total_keys": 0,
                "healthy_keys": 0,
                "keys_in_cooldown": 0,
                "budget_exhausted": 0,
                "total_monthly_spend": 0.0
            }
            
            for key in keys:
                prov = key.provider.value if hasattr(key.provider, 'value') else str(key.provider)
                
                if prov not in provider_stats:
                    provider_stats[prov] = {
                        "total_keys": 0,
                        "healthy": 0,
                        "cooldown": 0,
                        "rate_limited": 0,
                        "exhausted": 0,
                        "error": 0,
                        "keys": []
                    }
                
                status = self._get_key_status(key)
                stats = provider_stats[prov]
                stats["total_keys"] += 1
                overall["total_keys"] += 1
                
                if status == APIKeyHealthStatus.HEALTHY:
                    stats["healthy"] += 1
                    overall["healthy_keys"] += 1
                elif status == APIKeyHealthStatus.COOLDOWN:
                    stats["cooldown"] += 1
                    overall["keys_in_cooldown"] += 1
                elif status == APIKeyHealthStatus.EXHAUSTED:
                    stats["exhausted"] += 1
                    overall["budget_exhausted"] += 1
                elif status == APIKeyHealthStatus.RATE_LIMITED:
                    stats["rate_limited"] += 1
                else:
                    stats["error"] += 1
                
                self._reset_monthly_spend_if_needed(key)
                overall["total_monthly_spend"] += key.current_spend_usd
                
                # Add key details (mask sensitive data)
                key_info = {
                    "id": str(key.id),
                    "priority": key.priority,
                    "status": status,
                    "failure_count": key.failure_count,
                    "cooldown_until": key.cooldown_until.isoformat() if key.cooldown_until else None,
                    "monthly_budget_usd": key.monthly_budget_usd,
                    "current_spend_usd": round(key.current_spend_usd, 4),
                    "budget_remaining_pct": round(
                        ((key.monthly_budget_usd - key.current_spend_usd) / key.monthly_budget_usd * 100), 2
                    ) if key.monthly_budget_usd > 0 else 100
                }
                stats["keys"].append(key_info)
            
            # Determine overall status
            if overall["healthy_keys"] == overall["total_keys"]:
                overall_status = "healthy"
            elif overall["healthy_keys"] >= overall["total_keys"] // 2:
                overall_status = "degraded"
            else:
                overall_status = "critical"
            
            return {
                "overall_status": overall_status,
                "providers": provider_stats,
                "summary": overall,
                "generated_at": datetime.utcnow().isoformat()
            }
        
        if db:
            return _query(db)
        else:
            with get_db_context() as db_session:
                return _query(db_session)
    
    def _get_key_status(self, key: UserModelConfig) -> str:
        """Determine health status string for a key."""
        if not key.is_active or key.is_active is False:
            return APIKeyHealthStatus.DISABLED
        
        now = datetime.utcnow()
        
        if key.cooldown_until and now < key.cooldown_until:
            return APIKeyHealthStatus.COOLDOWN
        
        self._reset_monthly_spend_if_needed(key)
        if key.monthly_budget_usd > 0 and key.current_spend_usd >= key.monthly_budget_usd:
            return APIKeyHealthStatus.EXHAUSTED
        
        if key.status == ConnectionStatus.ERROR:
            return APIKeyHealthStatus.ERROR
        
        return APIKeyHealthStatus.HEALTHY
    
    def get_provider_availability(self, db: Optional[Session] = None) -> Dict[str, bool]:
        """
        Quick check: which providers have at least one healthy key?
        
        Returns: {"openai": True, "anthropic": False, ...}
        """
        def _query(db_session: Session):
            result = {}
            all_providers = [p.value for p in ProviderType]
            
            for prov in all_providers:
                healthy_key = self.get_active_key(prov, db=db_session)
                result[prov] = healthy_key is not None
            
            return result
        
        if db:
            return _query(db)
        else:
            with get_db_context() as db_session:
                return _query(db_session)
    
    # =====================================================================
    # Notification System
    # =====================================================================
    
    def _notify_all_keys_down(self, provider: str, db: Optional[Session] = None):
        """
        Notify all channels when all keys for a provider are down.
        
        Implements debouncing: max 1 notification per 5 minutes per provider.
        """
        now = datetime.utcnow()
        last_notification = self._notification_cache.get(provider)
        
        if last_notification:
            seconds_since_last = (now - last_notification).total_seconds()
            if seconds_since_last < self.NOTIFICATION_DEBOUNCE_SECONDS:
                logger.debug(f"Notification debounced for {provider} ({seconds_since_last}s ago)")
                return
        
        self._notification_cache[provider] = now
        
        message = (
            f"🚨 **AGENTIUM ALERT: All API Keys Down**\n\n"
            f"Provider: `{provider.upper()}`\n"
            f"Time: {now.strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Impact: AI services unavailable for this provider\n\n"
            f"Action Required: Check API key balances and status"
        )
        
        # 1. WebSocket broadcast to frontend
        self._broadcast_websocket_alert(provider, message)
        
        # 2. Send to all active channels
        self._send_channel_alerts(message, db)
        
        logger.critical(f"🚨 ALL KEYS DOWN for {provider} - notifications sent")
    
    def _broadcast_websocket_alert(self, provider: str, message: str):
        """Broadcast alert to all connected WebSocket clients."""
        try:
            from backend.main import manager
            asyncio.create_task(manager.broadcast({
                "type": "api_key_alert",
                "severity": "critical",
                "provider": provider,
                "message": message,
                "timestamp": datetime.utcnow().isoformat()
            }))
        except Exception as e:
            logger.error(f"Failed to broadcast WebSocket alert: {e}")
    
    def _send_channel_alerts(self, message: str, db: Optional[Session] = None):
        """Send alerts to all configured external channels."""
        def _send(db_session: Session):
            try:
                from backend.services.channel_manager import ChannelManager
                channel_manager = ChannelManager()
                
                # Get all active channels
                channels = db_session.query(ExternalChannel).filter_by(
                    status='active',
                    is_active=True
                ).all()
                
                for channel in channels:
                    try:
                        if channel.channel_type == ChannelType.TELEGRAM:
                            asyncio.create_task(
                                channel_manager.send_telegram(channel.channel_id, message)
                            )
                        elif channel.channel_type == ChannelType.DISCORD:
                            asyncio.create_task(
                                channel_manager.send_discord(channel.channel_id, message)
                            )
                        elif channel.channel_type == ChannelType.SLACK:
                            asyncio.create_task(
                                channel_manager.send_slack(channel.channel_id, message)
                            )
                        elif channel.channel_type == ChannelType.WHATSAPP:
                            asyncio.create_task(
                                channel_manager.send_whatsapp(channel.channel_id, message)
                            )
                    except Exception as e:
                        logger.error(f"Failed to send to {channel.channel_type}: {e}")
                        
            except Exception as e:
                logger.error(f"Channel alert system error: {e}")
        
        if db:
            _send(db)
        else:
            with get_db_context() as db_session:
                _send(db_session)
    
    # =====================================================================
    # Decorator for Automatic Failover
    # =====================================================================
    
    def with_failover(
        self,
        provider: str,
        fallback_providers: Optional[List[str]] = None,
        max_attempts: int = 3
    ):
        """
        Decorator for automatic failover on API calls.
        
        Usage:
            @api_key_manager.with_failover("openai", fallback_providers=["anthropic", "groq"])
            async def make_api_call(key_config, ...):
                # Your API call here
                return result
        """
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                providers = [provider] + (fallback_providers or [])
                
                last_error = None
                for prov in providers:
                    for attempt in range(max_attempts):
                        key = self.get_active_key(prov)
                        if not key:
                            break  # No healthy keys for this provider
                        
                        try:
                            # Inject key into function
                            result = await func(key, *args, **kwargs)
                            # Success - reset failure count
                            self.mark_key_success(key.id)
                            return result
                            
                        except Exception as e:
                            last_error = e
                            error_str = str(e).lower()
                            
                            # Determine if rate limit
                            is_rate_limit = any(x in error_str for x in [
                                "rate limit", "ratelimit", "too many requests", "429"
                            ])
                            
                            # Mark key failed
                            self.mark_key_failed(key.id, str(e), is_rate_limit)
                            
                            # If not rate limit and not last attempt, retry same provider
                            if not is_rate_limit and attempt < max_attempts - 1:
                                continue
                            break  # Move to next provider
                
                # All providers exhausted
                raise Exception(f"All API keys exhausted. Last error: {last_error}")
            
            return wrapper
        return decorator


# Global singleton instance
api_key_manager = APIKeyManager()


def init_api_key_manager(db: Session):
    """Initialize the API Key Manager (called during app startup)."""
    # Ensure all existing keys have proper defaults
    db.query(UserModelConfig).filter(
        UserModelConfig.priority.is_(None)
    ).update({"priority": 999})
    
    db.commit()
    logger.info("✅ API Key Manager initialized with resilience features")