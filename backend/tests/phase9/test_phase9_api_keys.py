"""
Phase 9.5 — API Key Resilience Tests
Tests for failover, budget enforcement, cooldown recovery, and all-keys-down notification.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timedelta


class TestAPIKeyFailover:
    """Tests for get_active_key_with_fallback() ordering."""

    def test_fallback_returns_first_healthy(self):
        from backend.services.api_key_manager import APIKeyManager
        mgr = APIKeyManager()

        # Mock: openai has no healthy keys, anthropic does
        key_mock = MagicMock()
        key_mock.id = "key-anthropic-1"

        def mock_get(provider, estimated_cost=0.0, db=None, min_priority=1):
            if provider == "anthropic":
                return key_mock
            return None

        mgr.get_active_key = mock_get

        result_key, result_provider = mgr.get_active_key_with_fallback(
            ["openai", "anthropic", "groq"]
        )
        assert result_key is key_mock
        assert result_provider == "anthropic"

    def test_all_exhausted_triggers_notification(self):
        from backend.services.api_key_manager import APIKeyManager
        mgr = APIKeyManager()

        # All providers return None
        mgr.get_active_key = MagicMock(return_value=None)
        mgr._notify_all_keys_down = MagicMock()

        result_key, result_provider = mgr.get_active_key_with_fallback(
            ["openai", "anthropic"]
        )
        assert result_key is None
        assert result_provider == "exhausted"
        mgr._notify_all_keys_down.assert_called_once()


class TestBudgetEnforcement:
    """Tests for budget checking logic."""

    def test_is_key_healthy_budget_exceeded(self):
        from backend.services.api_key_manager import APIKeyManager
        mgr = APIKeyManager()

        key = MagicMock()
        key.cooldown_until = None
        key.status = MagicMock()
        key.status.__eq__ = lambda self, other: False

        key.monthly_budget_usd = 10.0
        key.current_spend_usd = 9.5
        key.last_spend_reset = datetime.utcnow()

        # Estimated cost would exceed remaining budget
        result = mgr._is_key_healthy(key, estimated_cost=1.0)
        assert result is False

    def test_is_key_healthy_within_budget(self):
        from backend.services.api_key_manager import APIKeyManager
        mgr = APIKeyManager()

        key = MagicMock()
        key.cooldown_until = None
        key.status = MagicMock()
        key.status.__eq__ = lambda self, other: False

        key.monthly_budget_usd = 10.0
        key.current_spend_usd = 5.0
        key.last_spend_reset = datetime.utcnow()

        result = mgr._is_key_healthy(key, estimated_cost=1.0)
        assert result is True


class TestCooldownRecovery:
    """Tests for cooldown and recovery mechanics."""

    def test_auto_recover_resets_status(self):
        from backend.services.api_key_manager import APIKeyManager
        from backend.models.entities.user_config import ConnectionStatus

        mgr = APIKeyManager()
        key = MagicMock()
        key.failure_count = 5
        key.status = ConnectionStatus.ERROR

        mgr._auto_recover_key(key)

        assert key.status == ConnectionStatus.ACTIVE
        assert key.failure_count == 4  # Decay by 1

    def test_key_in_cooldown_not_healthy(self):
        from backend.services.api_key_manager import APIKeyManager
        mgr = APIKeyManager()

        key = MagicMock()
        key.cooldown_until = datetime.utcnow() + timedelta(minutes=10)
        key.monthly_budget_usd = 100.0
        key.current_spend_usd = 0.0
        key.last_spend_reset = datetime.utcnow()

        result = mgr._is_key_healthy(key)
        assert result is False


class TestMultiKeyVerification:
    """Tests for verify_multi_key_support()."""

    def test_verify_returns_expected_structure(self):
        from backend.services.api_key_manager import APIKeyManager
        mgr = APIKeyManager()

        key1 = MagicMock(id="k1", priority=1, failure_count=0, is_active=True)
        key2 = MagicMock(id="k2", priority=2, failure_count=0, is_active=True)

        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.order_by.return_value.all.return_value = [key1, key2]
        mgr.get_active_key = MagicMock(return_value=key1)
        mgr._get_key_status = MagicMock(return_value="healthy")

        result = mgr.verify_multi_key_support("openai", db=mock_db)

        assert result["provider"] == "openai"
        assert result["total_keys"] == 2
        assert result["multi_key_operational"] is True
        assert result["selected_key_id"] == str(key1.id)
        assert len(result["keys"]) == 2


class TestAPIKeyHealthStatus:
    """Tests for _get_key_status()."""

    def test_healthy_status(self):
        from backend.services.api_key_manager import APIKeyManager, APIKeyHealthStatus
        from backend.models.entities.user_config import ConnectionStatus
        mgr = APIKeyManager()

        key = MagicMock()
        key.is_active = True
        key.cooldown_until = None
        key.monthly_budget_usd = 0
        key.current_spend_usd = 0
        key.status = ConnectionStatus.ACTIVE
        key.last_spend_reset = datetime.utcnow()

        assert mgr._get_key_status(key) == APIKeyHealthStatus.HEALTHY

    def test_disabled_status(self):
        from backend.services.api_key_manager import APIKeyManager, APIKeyHealthStatus
        mgr = APIKeyManager()

        key = MagicMock()
        key.is_active = False

        assert mgr._get_key_status(key) == APIKeyHealthStatus.DISABLED

    def test_cooldown_status(self):
        from backend.services.api_key_manager import APIKeyManager, APIKeyHealthStatus
        mgr = APIKeyManager()

        key = MagicMock()
        key.is_active = True
        key.cooldown_until = datetime.utcnow() + timedelta(minutes=5)

        assert mgr._get_key_status(key) == APIKeyHealthStatus.COOLDOWN
