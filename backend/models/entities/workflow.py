"""
WorkflowExecution and WorkflowSubTask — persist multi-step workflow state.

Non-breaking addition: creates two NEW tables (workflow_executions,
workflow_subtasks). No existing table is altered here; the migration
006_workflow.py handles the three new columns on the tasks table.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, Text, DateTime, Integer, ForeignKey, JSON
)
from sqlalchemy.orm import relationship

from backend.models.entities.base import Base


class WorkflowExecution(Base):
    """Top-level record that tracks the lifecycle of a multi-step workflow."""

    __tablename__ = "workflow_executions"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    workflow_id = Column(String(64), unique=True, nullable=False, index=True)
    original_message = Column(Text, nullable=False)
    status = Column(String(32), default="pending", nullable=False, index=True)
    # Shared context written by each completed sub-task and read by dependents
    context_data = Column(JSON, default=dict, nullable=False)
    error = Column(Text, nullable=True)
    created_by = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )
    completed_at = Column(DateTime, nullable=True)

    subtasks = relationship(
        "WorkflowSubTask",
        back_populates="workflow",
        cascade="all, delete-orphan",
        order_by="WorkflowSubTask.step_index",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "original_message": self.original_message,
            "status": self.status,
            "context_data": self.context_data or {},
            "error": self.error,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "subtasks": [s.to_dict() for s in (self.subtasks or [])],
        }


class WorkflowSubTask(Base):
    """
    One atomic step inside a WorkflowExecution.

    Named WorkflowSubTask (table: workflow_subtasks) to avoid any conflict
    with the existing SubTask model (table: subtasks) in task.py.
    """

    __tablename__ = "workflow_subtasks"

    id = Column(
        String(36), primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    workflow_id = Column(
        String(64),
        ForeignKey("workflow_executions.workflow_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step_index = Column(Integer, nullable=False, default=0)

    # The registered tool name, e.g. "fetch_stock_price"
    intent = Column(String(128), nullable=False)
    # Input params resolved at planning time
    params = Column(JSON, default=dict, nullable=False)
    # List of intent names that must complete before this task starts
    depends_on = Column(JSON, default=list, nullable=False)

    status = Column(String(32), default="pending", nullable=False, index=True)
    # Output written here on success; read by downstream tasks via context
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Celery task ID for deferred sub-tasks; enables cancellation/status checks
    celery_task_id = Column(String(256), nullable=True)
    schedule_offset_days = Column(Integer, default=0, nullable=False)
    scheduled_for = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    workflow = relationship("WorkflowExecution", back_populates="subtasks")

    def to_dict(self):
        return {
            "id": self.id,
            "workflow_id": self.workflow_id,
            "step_index": self.step_index,
            "intent": self.intent,
            "params": self.params or {},
            "depends_on": self.depends_on or [],
            "status": self.status,
            "result": self.result,
            "error": self.error,
            "celery_task_id": self.celery_task_id,
            "schedule_offset_days": self.schedule_offset_days,
            "scheduled_for": (
                self.scheduled_for.isoformat() if self.scheduled_for else None
            ),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }