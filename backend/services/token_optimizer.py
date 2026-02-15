"""
Enhanced Token Optimizer with intelligent model allocation and API pooling.
Manages token usage, cost optimization, and model switching.
"""

import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.models.entities.agents import Agent, AgentStatus, AgentType
from backend.models.entities.task import Task, TaskStatus, TaskPriority
from backend.services.api_manager import init_api_manager, ModelCapability
import backend.services.api_manager as api_manager_module
from backend.services.model_allocation import init_model_allocator, model_allocator


class TokenOptimizer:
    """
    Enhanced Token Optimizer that:
    1. Tracks token usage per agent
    2. Automatically selects optimal models per task
    3. Manages idle/active transitions with cost awareness
    4. Integrates with hierarchical agent system
    """
    
    def __init__(self):
        self.idle_mode_active = False
        self.last_activity_at = datetime.utcnow()
        self.idle_threshold_seconds = 60  # Configurable
        
        # Token tracking
        self.tokens_used_by_agent: Dict[str, int] = {}  # agentium_id -> tokens
        self.total_tokens_saved_today = 0
        self.last_budget_reset = datetime.utcnow()
        
        # Model allocation tracking
        self.active_model_configs: Dict[str, str] = {}  # agent_id -> config_id
        self.idle_model_configs: Dict[str, str] = {}    # agent_id -> local_config_id
        
        # Persistent agents (Head + 2 Council)
        self.persistent_agents: List[str] = ["00001", "10001", "10002"]  # Default
        
        # Singleton pattern
        self.initialized = False
    
    @property
    def active_budget(self):
        """Return the budget manager (for compatibility with main.py)."""
        return idle_budget
    
    def initialize(self, db: Session, agents: List[Agent] = None):
        """Initialize with database session and agent list."""
        if self.initialized:
            return
        
        # Load persistent agents from DB if provided
        if agents:
            self.persistent_agents = [a.agentium_id for a in agents if a.is_persistent]
        
        # Initialize model allocator if not already done
        if model_allocator is None:
            init_model_allocator(db)
        
        # Get local model config for idle mode
        self.idle_model_key = "local:kimi-2.5-7b"  # Default idle model
        
        self.initialized = True
    
    def record_activity(self):
        """Record user activity and wake from idle if needed."""
        self.last_activity_at = datetime.utcnow()
        
        # Wake system immediately - but we need db, so just flag it
        if self.idle_mode_active:
            # Schedule wake with proper db context
            from backend.models.database import get_db_context
            async def _wake():
                with get_db_context() as db:
                    await self.wake_from_idle(db)
            asyncio.create_task(_wake())
    
    def calculate_token_savings(self, task_type: str, duration_seconds: int) -> int:
        """
        Calculate tokens saved by running a task in idle mode vs active mode.
        Idle mode uses cheaper/local models, resulting in savings.
        """
        # Base tokens per minute for different task types
        tokens_per_minute = {
            'audit_archival': 50,
            'storage_dedupe': 100,
            'vector_maintenance': 150,
            'cache_optimization': 80,
            'predictive_planning': 200,
            'constitution_refine': 120,
            'ethos_optimization': 90,
            'agent_health_scan': 60,
            'default': 100
        }
        
        # Get base rate for this task type
        base_rate = tokens_per_minute.get(task_type, tokens_per_minute['default'])
        
        # Calculate duration in minutes
        duration_minutes = duration_seconds / 60
        
        # Idle mode uses ~20% of active mode tokens (80% savings)
        idle_efficiency = 0.2
        
        # Calculate savings: (active_cost - idle_cost) * duration
        active_tokens = base_rate * duration_minutes
        idle_tokens = active_tokens * idle_efficiency
        savings = int(active_tokens - idle_tokens)
        
        return max(0, savings)  # Ensure non-negative
    
    async def check_idle_transition(self, db: Session) -> bool:
        """
        Check if system should transition to/from idle mode.
        Returns True if state changed.
        """
        idle_duration = (datetime.utcnow() - self.last_activity_at).total_seconds()
        should_be_idle = idle_duration > self.idle_threshold_seconds
        
        if should_be_idle and not self.idle_mode_active:
            await self.enter_idle_mode(db)
            return "entered_idle"
        elif not should_be_idle and self.idle_mode_active:
            await self.wake_from_idle(db)
            return "exited_idle"
        
        return "no_change"
    
    async def enter_idle_mode(self, db: Session):
        """
        Enter idle mode: Switch ALL agents to local models,
        but only allow persistent agents to continue idle tasks.
        """
        print("🌙 ENTERING IDLE MODE - Switching to local models")
        
        self.idle_mode_active = True
        
        # Get local model (the "lowest" model)
        local_model = api_manager_module.api_manager._get_best_local_model()
        
        # Update all persistent agents to local model
        agents = db.query(Agent).filter(
            Agent.agentium_id.in_(self.persistent_agents),
            Agent.status != AgentStatus.TERMINATED
        ).all()
        
        for agent in agents:
            # Cache active config
            if agent.preferred_config_id:
                self.active_model_configs[agent.id] = agent.preferred_config_id
            
            # Allocate local model
            new_config_id = model_allocator._ensure_agent_has_config(agent, local_model).id
            agent.preferred_config_id = new_config_id
            agent.idle_mode_enabled = True
            agent.status = AgentStatus.IDLE_WORKING
        
        # Stop non-persistent agents to free resources
        non_persistent = db.query(Agent).filter(
            ~Agent.agentium_id.in_(self.persistent_agents),
            Agent.status == AgentStatus.ACTIVE
        ).all()
        
        for agent in non_persistent:
            agent.status = AgentStatus.IDLE_PAUSED
        
        db.commit()
        
        # Broadcast status
        await self._broadcast_idle_status("entered_idle", {
            'agents_switched': len(agents),
            'budget_status': idle_budget.get_status()
        })
        
        print(f"✅ {len(agents)} agents switched to {local_model.model_name}")
    
    async def wake_from_idle(self, db: Session):
        """
        Wake from idle: Restore original models for all agents.
        Re-run model allocation to get optimal models for current tasks.
        """
        print("☀️ WAKING FROM IDLE MODE - Restoring optimized models")
        
        self.idle_mode_active = False
        self.last_activity_at = datetime.utcnow()
        
        # Restore active models for all agents (re-optimize)
        all_agents = db.query(Agent).filter(Agent.status != AgentStatus.TERMINATED).all()
        
        for agent in all_agents:
            # Get or create optimized model allocation
            current_task = db.query(Task).filter_by(
                assigned_to_agent_id=agent.id,
                status=TaskStatus.RUNNING
            ).first()
            
            # Allocate optimal model for this agent's current/future task
            if current_task:
                new_config_id = model_allocator.allocate_model(agent, current_task).id
            else:
                # Default allocation based on tier
                new_config_id = model_allocator.allocate_model(agent, None).id
            
            agent.preferred_config_id = new_config_id
            agent.idle_mode_enabled = False
            
            # Wake non-persistent agents
            if agent.agentium_id not in self.persistent_agents:
                agent.status = AgentStatus.ACTIVE
        
        # Clear idle configs
        self.idle_model_configs.clear()
        
        # Resume any paused agents/tasks
        db.commit()
        
        await self._broadcast_idle_status("exited_idle", {
            'agents_restored': len(all_agents),
            'allocation_report': model_allocator.get_allocation_report()
        })
        
        print(f"✅ {len(all_agents)} agents restored to optimal models")
    
    async def allocate_for_task(self, agent: Agent, task: Task) -> str:
        """
        Allocate optimal model for a specific task.
        This is called when task is assigned to agent.
        
        Returns: UserModelConfig.id
        """
        # Initial allocation
        config_id = model_allocator.allocate_model(agent, task)
        
        # Store allocation
        self.active_model_configs[agent.id] = config_id
        
        # Log for token tracking
        model_key = f"{agent.preferred_config.provider}:{agent.preferred_config.default_model}"
        estimated_tokens = self.estimate_task_tokens(task)
        
        # Adjust budget
        idle_budget.record_usage(estimated_tokens // 1000)  # Rough estimate
        
        # Log allocation
        await self._log_allocation(agent, task, config_id)
        
        return config_id
    
    def estimate_task_tokens(self, task: Task) -> int:
        """
        Estimate token usage for a task based on type and complexity.
        Used for budget planning.
        """
        # Base estimates by task type
        base_estimates = {
            TaskType.SIMPLE_QUERY: 500,
            TaskType.CONFIRMATION: 200,
            TaskType.CODE_GENERATION: 3000,
            TaskType.CODE_REVIEW: 2000,
            TaskType.DEBUGGING: 2500,
            TaskType.SYSTEM_ANALYSIS: 4000,
            TaskType.PLANNING: 3500,
            TaskType.DECISION: 2000,
            TaskType.RESEARCH: 5000,
            TaskType.CREATIVE_WRITING: 1500,
            TaskType.BRAINSTORMING: 1000,
            TaskType.DOCUMENTATION: 2000,
            TaskType.NOTIFICATION: 300,
        }
        
        base = base_estimates.get(task.task_type, 1000)
        
        # Adjust for priority
        priority_multiplier = {
            TaskPriority.CRITICAL: 1.5,
            TaskPriority.HIGH: 1.2,
            TaskPriority.NORMAL: 1.0,
            TaskPriority.LOW: 0.8,
            TaskPriority.IDLE: 0.5
        }
        
        return int(base * priority_multiplier.get(task.priority, 1.0))
    
    def record_token_usage(self, agentium_id: str, tokens_used: int, model_key: str):
        """
        Record actual token usage for tracking and optimization.
        """
        # Per-agent tracking
        current = self.tokens_used_by_agent.get(agentium_id, 0)
        self.tokens_used_by_agent[agentium_id] = current + tokens_used
        
        # Total savings (compared to using best model)
        model = api_manager_module.api_manager.models.get(model_key)
        if model:
            # Savings = (best_model_cost - current_model_cost) * tokens
            best_model = api_manager_module.api_manager._get_best_available_model_by_capability(ModelCapability.CODE)
            savings = (best_model.cost_per_1k_tokens - model.cost_per_1k_tokens) * (tokens_used / 1000)
            self.total_tokens_saved_today += int(savings)
        
        # Check budget reset
        self._check_daily_reset()
    
    def _check_daily_reset(self):
        """Reset daily counters if it's a new day."""
        now = datetime.utcnow()
        if now.date() > self.last_budget_reset.date():
            self.tokens_used_by_agent.clear()
            self.total_tokens_saved_today = 0
            self.last_budget_reset = now
    
    def get_cost_report(self, db: Session) -> Dict[str, Any]:
        """
        Generate comprehensive cost/token usage report.
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "idle_mode": self.idle_mode_active,
            "tokens_by_agent": self.tokens_used_by_agent.copy(),
            "total_saved_today": self.total_tokens_saved_today,
            "budget_status": idle_budget.get_status(),
            "allocation_report": model_allocator.get_allocation_report(),
            "hourly_cost_estimate": self._calculate_hourly_cost(db)
        }
    
    def _calculate_hourly_cost(self, db: Session) -> float:
        """
        Estimate hourly cost based on current model allocations.
        """
        agents = db.query(Agent).filter_by(is_active='Y').all()
        hourly_cost = 0.0
        
        for agent in agents:
            if not agent.preferred_config:
                continue
            
            model_key = f"{agent.preferred_config.provider}:{agent.preferred_config.default_model}"
            model = api_manager_module.api_manager.models.get(model_key)
            
            if model:
                # Assume average 1000 tokens per hour per agent
                hourly_cost += model.cost_per_1k_tokens
        
        return hourly_cost
    
    async def _log_allocation(self, agent: Agent, task: Task, config_id: str):
        """Log model allocation decision."""
        from backend.models.database import get_db_context
        
        with get_db_context() as db:
            audit = AuditLog(
                level=AuditLevel.INFO,
                category=AuditCategory.SYSTEM,
                actor_type='system',
                actor_id='model_allocator',
                action='model_assigned',
                target_type='agent',
                target_id=agent.agentium_id,
                description=f"Assigned model {config_id} for task {task.agentium_id}",
                before_state={
                    'agent_tier': agent.agentium_id[0],
                    'task_type': task.task_type.value,
                    'task_priority': task.priority.value
                },
                after_state={
                    'model_config_id': config_id,
                    'estimated_cost': self.estimate_task_tokens(task) // 1000 * 0.01
                },
                created_at=datetime.utcnow()
            )
            db.add(audit)
            db.commit()
    
    async def _broadcast_idle_status(self, event: str, data: Dict):
        """Broadcast status to WebSocket clients."""
        try:
            from backend.main import manager
            await manager.broadcast({
                "type": "optimizer_status",
                "event": event,
                "data": data,
                "timestamp": datetime.utcnow().isoformat()
            })
        except ImportError:
            print(f"⚠️ WebSocket manager not available")
    
    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive optimizer status."""
        idle_duration = (datetime.utcnow() - self.last_activity_at).total_seconds()
        
        return {
            "idle_mode_active": self.idle_mode_active,
            "time_since_last_activity_seconds": idle_duration,
            "idle_threshold_seconds": self.idle_threshold_seconds,
            "total_agents_monitored": len(self.tokens_used_by_agent),
            "total_tokens_saved_today": self.total_tokens_saved_today,
            "budget_status": idle_budget.get_status(),
            "is_single_api_mode": api_manager_module.api_manager.single_api_mode()
        }


# Enhanced Budget Manager with cost tracking
class IdleBudgetManager:
    """
    Enhanced token budget that tracks both tokens and estimated cost.
    Prevents runaway spending even during idle operations.
    """
    
    def __init__(self, daily_token_limit: int = 100000, daily_cost_limit: float = 10.0):
        self.daily_token_limit = daily_token_limit
        self.daily_cost_limit = daily_cost_limit  # USD
        
        self.tokens_used_today = 0
        self.cost_used_today = 0.0
        self.last_reset = datetime.utcnow()
        
        # Cost multiplier for idle vs active (idle is cheaper)
        self.idle_cost_multiplier = 0.0  # Local models are free
        
        # Initialize tracking for main.py compatibility
        self._total_tokens_saved = 0
        self._total_cost_saved = 0.0
    
    @property
    def daily_idle_budget_usd(self):
        """Daily budget for idle mode operations (compatibility with main.py)."""
        return self.daily_cost_limit
    
    @property
    def daily_cost_limit_usd(self):
        """Daily cost limit in USD (compatibility with main.py)."""
        return self.daily_cost_limit
    
    @property
    def total_tokens_saved(self):
        """Total tokens saved (compatibility with main.py)."""
        return self._total_tokens_saved
    
    @property
    def total_cost_saved_usd(self):
        """Total cost saved in USD (compatibility with main.py)."""
        return self._total_cost_saved
    
    def check_budget(self, estimated_cost: float) -> bool:
        """Check if operation fits within daily budget."""
        self._check_reset()
        return (self.cost_used_today + estimated_cost) <= self.daily_cost_limit
    
    def record_usage(self, tokens: int, model_cost_per_1k: float = 0.0, is_idle: bool = False):
        """Record token usage and calculate cost."""
        self._check_reset()
        
        self.tokens_used_today += tokens
        
        # Calculate cost (local models cost 0)
        cost_multiplier = self.idle_cost_multiplier if is_idle else 1.0
        cost = (tokens / 1000) * model_cost_per_1k * cost_multiplier
        
        self.cost_used_today += cost
    
    def get_status(self) -> Dict[str, Any]:
        """Get detailed budget status."""
        self._check_reset()
        
        return {
            "daily_token_limit": self.daily_token_limit,
            "tokens_used_today": self.tokens_used_today,
            "tokens_remaining": self.daily_token_limit - self.tokens_used_today,
            "daily_cost_limit_usd": self.daily_cost_limit,
            "cost_used_today_usd": round(self.cost_used_today, 4),
            "cost_remaining_usd": round(self.daily_cost_limit - self.cost_used_today, 4),
            "cost_percentage_used": round((self.cost_used_today / self.daily_cost_limit) * 100, 2) if self.daily_cost_limit > 0 else 0,
            "cost_percentage_tokens": round((self.tokens_used_today / self.daily_token_limit) * 100, 2) if self.daily_token_limit > 0 else 0
        }
    
    def _check_reset(self):
        """Reset daily counters at midnight."""
        now = datetime.utcnow()
        if now.date() > self.last_reset.date():
            self.tokens_used_today = 0
            self.cost_used_today = 0.0
            self.last_reset = now


# Singleton instances
token_optimizer = TokenOptimizer()
idle_budget = IdleBudgetManager(daily_token_limit=100000, daily_cost_limit=5.0)  # $5/day limit

# Initialization function
def init_token_optimizer(db: Session, agents: List[Agent] = None):
    """Initialize token optimizer with database and agents."""
    token_optimizer.initialize(db, agents)
    
    # Initialize API manager if needed
    if api_manager_module.api_manager is None:
        init_api_manager(db)