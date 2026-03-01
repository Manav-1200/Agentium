"""
Phase 9.1 — Monitoring & Observability Tests
Tests for AlertManager dispatch, format, and MonitoringService background logic.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime


class TestAlertManagerFormat:
    """Tests for AlertManager._format_alert_message()."""

    def _make_alert(self, severity_value="critical", alert_type="test_alert"):
        alert = MagicMock()
        alert.severity.value = severity_value
        alert.alert_type = alert_type
        alert.created_at = datetime(2025, 1, 1, 12, 0, 0)
        alert.message = "Test message"
        alert.detected_by_agent_id = "system"
        alert.affected_agent_id = None
        return alert

    def test_format_critical_alert(self, mock_db):
        from backend.services.alert_manager import AlertManager
        mgr = AlertManager(mock_db)
        alert = self._make_alert("critical", "critical_violation")
        msg = mgr._format_alert_message(alert)
        assert "CRITICAL" in msg
        assert "critical_violation" in msg
        assert "Test message" in msg

    def test_format_minor_alert(self, mock_db):
        from backend.services.alert_manager import AlertManager
        mgr = AlertManager(mock_db)
        alert = self._make_alert("minor", "info_notice")
        msg = mgr._format_alert_message(alert)
        assert "MINOR" in msg
        assert "ℹ️" in msg

    def test_format_critic_veto_alert(self, mock_db):
        from backend.services.alert_manager import AlertManager
        mgr = AlertManager(mock_db)
        alert = self._make_alert("major", "critic_veto")
        msg = mgr._format_alert_message(alert)
        assert "🛑" in msg

    def test_format_all_keys_down_alert(self, mock_db):
        from backend.services.alert_manager import AlertManager
        mgr = AlertManager(mock_db)
        alert = self._make_alert("critical", "all_api_keys_down")
        msg = mgr._format_alert_message(alert)
        assert "🔑❌" in msg

    def test_format_emergency_alert(self, mock_db):
        from backend.services.alert_manager import AlertManager
        mgr = AlertManager(mock_db)
        alert = self._make_alert("critical", "emergency")
        msg = mgr._format_alert_message(alert)
        assert "🆘" in msg

    def test_format_systemwide_affected(self, mock_db):
        from backend.services.alert_manager import AlertManager
        mgr = AlertManager(mock_db)
        alert = self._make_alert()
        alert.affected_agent_id = None
        msg = mgr._format_alert_message(alert)
        assert "System-wide" in msg


class TestAlertManagerDispatch:
    """Tests for AlertManager.dispatch_alert() routing logic."""

    @pytest.mark.asyncio
    async def test_critical_triggers_websocket(self, mock_db):
        from backend.services.alert_manager import AlertManager
        mgr = AlertManager(mock_db)
        mgr._broadcast_websocket = AsyncMock()
        mgr._notify_external_channels = AsyncMock()
        mgr._send_email_alert = AsyncMock()
        mgr._send_webhook_alert = AsyncMock()
        mgr._escalate_critical_alert = MagicMock()

        alert = MagicMock()
        alert.severity.value = "critical"
        alert.alert_type = "test"
        alert.message = "Critical test"
        alert.created_at = datetime.utcnow()

        # ViolationSeverity.CRITICAL enum comparison
        from backend.models.entities.monitoring import ViolationSeverity
        alert.severity = ViolationSeverity.CRITICAL
        alert.detected_by_agent_id = "system"
        alert.affected_agent_id = None

        await mgr.dispatch_alert(alert)

        mgr._broadcast_websocket.assert_called_once()
        mgr._escalate_critical_alert.assert_called_once()
        mgr._send_email_alert.assert_called_once()

    @pytest.mark.asyncio
    async def test_minor_skips_websocket(self, mock_db):
        from backend.services.alert_manager import AlertManager
        from backend.models.entities.monitoring import ViolationSeverity

        mgr = AlertManager(mock_db)
        mgr._broadcast_websocket = AsyncMock()
        mgr._notify_external_channels = AsyncMock()
        mgr._send_email_alert = AsyncMock()
        mgr._send_webhook_alert = AsyncMock()
        mgr._escalate_critical_alert = MagicMock()

        alert = MagicMock()
        alert.severity = ViolationSeverity.MINOR
        alert.alert_type = "info"
        alert.message = "Minor notice"
        alert.created_at = datetime.utcnow()
        alert.detected_by_agent_id = "system"
        alert.affected_agent_id = None

        await mgr.dispatch_alert(alert)

        mgr._broadcast_websocket.assert_not_called()
        mgr._escalate_critical_alert.assert_not_called()


class TestAlertManagerEmail:
    """Tests for email alert functionality."""

    @pytest.mark.asyncio
    async def test_email_skipped_when_not_configured(self, mock_db):
        """Email alert should be silently skipped if SMTP is not configured."""
        from backend.services.alert_manager import AlertManager

        with patch("backend.services.alert_manager.settings") as mock_settings:
            mock_settings.SMTP_HOST = None
            mock_settings.ALERT_EMAIL_TO = None

            mgr = AlertManager(mock_db)
            alert = MagicMock()
            # Should return immediately without error
            await mgr._send_email_alert(alert, "Test message")


class TestAlertManagerWebhook:
    """Tests for webhook alert functionality."""

    @pytest.mark.asyncio
    async def test_webhook_skipped_when_not_configured(self, mock_db):
        """Webhook alert should be silently skipped if URL is not configured."""
        from backend.services.alert_manager import AlertManager

        with patch("backend.services.alert_manager.settings") as mock_settings:
            mock_settings.WEBHOOK_ALERT_URL = None

            mgr = AlertManager(mock_db)
            alert = MagicMock()
            await mgr._send_webhook_alert(alert, "Test message")
