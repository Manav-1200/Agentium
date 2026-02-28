"""
Alert Manager for Agentium (Phase 9)
Handles system-wide alerts, notifications, and escalation to the appropriate channels.
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import logging
import asyncio

from backend.models.entities.agents import Agent, AgentType
from backend.models.entities.monitoring import MonitoringAlert, ViolationSeverity
from backend.models.entities.channels import ExternalChannel, ChannelType
from backend.services.channel_manager import ChannelManager

# NOTE: websocket_manager is imported lazily (inside methods) to avoid a circular import.
# backend.main imports db_maintenance → alert_manager, so importing backend.main here
# at module level causes: ImportError: cannot import name 'manager' from partially
# initialized module 'backend.main'.

logger = logging.getLogger(__name__)

class AlertManager:
    """Central service for managing and dispatching system alerts."""

    def __init__(self, db: Session):
        self.db = db
        self.channel_manager = ChannelManager()

    async def dispatch_alert(self, alert: MonitoringAlert):
        """Dispatch an alert to the configured channels based on severity."""
        
        # 1. Format the alert message
        message = self._format_alert_message(alert)
        logger.info(f"Dispatching Alert [{alert.severity.value}]: {alert.alert_type} - {alert.message}")

        # 2. Always broadcast critical/major alerts to WebSocket
        if alert.severity in [ViolationSeverity.CRITICAL, ViolationSeverity.MAJOR, ViolationSeverity.MODERATE]:
            await self._broadcast_websocket(alert, message)

        # 3. Route to external channels based on severity and configuration
        await self._notify_external_channels(alert, message)

        # 4. Escalate to Head of Council / Sovereign if Critical
        if alert.severity == ViolationSeverity.CRITICAL:
            self._escalate_critical_alert(alert)

    def _format_alert_message(self, alert: MonitoringAlert) -> str:
        """Format an alert into a readable message string."""
        severity_icons = {
            ViolationSeverity.MINOR: "ℹ️",
            ViolationSeverity.MODERATE: "⚠️",
            ViolationSeverity.MAJOR: "🚨",
            ViolationSeverity.CRITICAL: "💀"
        }
        icon = severity_icons.get(alert.severity, "🔔")
        
        timestamp = alert.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')
        return (
            f"{icon} **AGENTIUM SYSTEM ALERT: {alert.severity.value.upper()}**\n\n"
            f"Type: `{alert.alert_type}`\n"
            f"Time: {timestamp}\n"
            f"Message: {alert.message}\n"
            f"Detected By: `{alert.detected_by_agent_id}`\n"
            f"Affected Agent: `{alert.affected_agent_id or 'System-wide'}`"
        )

    async def _broadcast_websocket(self, alert: MonitoringAlert, message: str):
        """Broadcast alert to all connected WebSocket clients (Frontend Dashboard)."""
        try:
            # Lazy import to avoid circular dependency with backend.main
            from backend.main import manager as websocket_manager
            await websocket_manager.broadcast({
                "type": "system_alert",
                "severity": alert.severity.value,
                "alert_type": alert.alert_type,
                "message": message,
                "timestamp": alert.created_at.isoformat()
            })
        except Exception as e:
            logger.error(f"Failed to broadcast WebSocket alert: {e}")

    async def _notify_external_channels(self, alert: MonitoringAlert, message: str):
        """Send alerts to configured external messaging channels (Slack, Discord, Telegram, etc.)."""
        # Only notify channels for MAJOR and CRITICAL alerts
        if alert.severity not in [ViolationSeverity.MAJOR, ViolationSeverity.CRITICAL]:
            return

        try:
            # Fetch active channels
            active_channels = self.db.query(ExternalChannel).filter_by(
                status='active',
                is_active=True
            ).all()

            for channel in active_channels:
                try:
                    if channel.channel_type == ChannelType.TELEGRAM:
                        asyncio.create_task(self.channel_manager.send_telegram(channel.channel_id, message))
                    elif channel.channel_type == ChannelType.DISCORD:
                        asyncio.create_task(self.channel_manager.send_discord(channel.channel_id, message))
                    elif channel.channel_type == ChannelType.SLACK:
                        asyncio.create_task(self.channel_manager.send_slack(channel.channel_id, message))
                    elif channel.channel_type == ChannelType.WHATSAPP:
                        asyncio.create_task(self.channel_manager.send_whatsapp(channel.channel_id, message))
                except Exception as channel_err:
                    logger.error(f"Failed to send alert to channel {channel.id} ({channel.channel_type}): {channel_err}")
        except Exception as e:
            logger.error(f"Error querying channels for alerts: {e}")

    def _escalate_critical_alert(self, alert: MonitoringAlert):
        """Escalation protocol for critical system failures or constitutional violations."""
        # Find the Head of Council to associate the alert or trigger emergency subroutines
        head = self.db.query(Agent).filter_by(agent_type=AgentType.HEAD_OF_COUNCIL).first()
        if head:
            # Here we could spawn an emergency task for the Head of Council
            logger.critical(f"Alert escalated to Head of Council ({head.agentium_id}): {alert.alert_type}")

def get_alert_manager(db: Session) -> AlertManager:
    return AlertManager(db)