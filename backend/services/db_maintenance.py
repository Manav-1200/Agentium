"""
Database Maintenance and Backup Service for Agentium (Phase 9)
Handles audit log archival, task history cleanup, and triggers basic snapshot logical backups.
"""

from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import logging
import asyncio
import os
import subprocess

from backend.models.database import get_db_context
from backend.models.entities.audit import AuditLog
from backend.models.entities.task import Task
from backend.services.alert_manager import AlertManager
from backend.models.entities.monitoring import MonitoringAlert, ViolationSeverity
from backend.core.config import settings
from backend.models.database import get_system_agent_id

logger = logging.getLogger(__name__)

class DatabaseMaintenanceService:
    """Handles routine database cleanup, archival, and trigger for backups."""

    @staticmethod
    async def cleanup_stale_data():
        """
        Background task: Daily deletes old audit logs and archives ancient tasks to save Postgres Memory.
        Phase 9.2: Memory Management Requirement
        """
        while True:
            try:
                with get_db_context() as db:
                    alert_manager = AlertManager(db)
                    
                    # 1. Clean up Audit Logs older than 30 days
                    cutoff_30_days = datetime.utcnow() - timedelta(days=30)
                    deleted_audit_logs = db.query(AuditLog).filter(AuditLog.created_at < cutoff_30_days).delete()
                    
                    # 2. Archive completed tasks older than 90 days (for now, simply soft-delete or remove)
                    cutoff_90_days = datetime.utcnow() - timedelta(days=90)
                    deleted_tasks = db.query(Task).filter(
                        Task.status.in_(["completed", "cancelled", "failed"]),
                        Task.updated_at < cutoff_90_days
                    ).delete()

                    db.commit()

                    if deleted_audit_logs > 0 or deleted_tasks > 0:
                        logger.info(f"DB Maintenance: Cleared {deleted_audit_logs} old audit logs & {deleted_tasks} old tasks.")
            
            except Exception as e:
                logger.error(f"Error in DB cleanup routine: {e}")
            
            await asyncio.sleep(86400)  # Sleep 24 hours

    @staticmethod
    async def trigger_pg_dump():
        """
        Triggers a local pg_dump backup script.
        Phase 9.3: Backup & Disaster Recovery
        """
        while True:
            try:
                # We expect the DB URL in the env vars
                db_url = os.getenv("DATABASE_URL")
                backup_dir = os.getenv("BACKUP_DIR", "/tmp/agentium_backups")
                
                if db_url and "postgresql" in db_url:
                    if not os.path.exists(backup_dir):
                        os.makedirs(backup_dir, exist_ok=True)
                        
                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    backup_file = os.path.join(backup_dir, f"backup_{timestamp}.sql")
                    
                    # Note: in real prod, we would use a proper postgres runner, this is an indicative execution call
                    command = f"pg_dump {db_url} > {backup_file}"
                    
                    process = await asyncio.create_subprocess_shell(
                        command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode == 0:
                        logger.info(f"Database backup successful: {backup_file}")
                    else:
                        logger.error(f"Database backup failed: {stderr.decode()}")
                        with get_db_context() as db:
                            am = AlertManager(db)
                            alert = MonitoringAlert(
                                alert_type="backup_failure",
                                severity=ViolationSeverity.CRITICAL,
                                detected_by_agent_id=get_system_agent_id(db),
                                affected_agent_id=None,
                                message=f"Daily PostgreSQL backup failed: {stderr.decode()}"
                            )
                            db.add(alert)
                            db.commit()
                            await am.dispatch_alert(alert)

            except Exception as e:
                logger.error(f"Error triggering pg_dump: {e}")
                
            await asyncio.sleep(86400)  # Daily Backups

    @classmethod
    def start_maintenance_monitors(cls):
        """Starts the detached asynchronous maintenance loops."""
        asyncio.create_task(cls.cleanup_stale_data())
        asyncio.create_task(cls.trigger_pg_dump())
