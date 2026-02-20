"""
Pydantic schemas for Task API.
Updated for Task Execution Architecture: Governance Alignment
"""
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, List, Any

from backend.models.entities.task import TaskStatus, TaskType, TaskPriority


class AssignedAgents(BaseModel):
    head: Optional[str] = None
    lead: Optional[str] = None
    task_agents: List[str] = []

    class Config:
        extra = "allow"


class GovernanceInfo(BaseModel):
    """NEW: Governance-related fields."""
    constitutional_basis: Optional[str] = None
    hierarchical_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    execution_plan_id: Optional[str] = None
    recurrence_pattern: Optional[str] = None  # Cron expression for recurring tasks
    requires_deliberation: bool = True
    council_approved: bool = False
    head_approved: bool = False

    class Config:
        extra = "allow"


class ErrorInfo(BaseModel):
    """NEW: Error tracking information."""
    error_count: int = 0
    retry_count: int = 0
    max_retries: int = 5
    last_error: Optional[str] = None

    class Config:
        extra = "allow"


class TaskCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    priority: str = Field(default="normal")
    task_type: str = Field(default="execution")
    # NEW: Governance fields
    constitutional_basis: Optional[str] = Field(None, description="Constitutional justification for task")
    hierarchical_id: Optional[str] = Field(None, description="Hierarchical dot-notated ID")
    parent_task_id: Optional[str] = Field(None, description="Parent task ID for hierarchical tasks")
    execution_plan_id: Optional[str] = Field(None, description="Linked execution plan ID")
    recurrence_pattern: Optional[str] = Field(None, description="Cron expression for recurring tasks")

    @validator("priority")
    def validate_priority(cls, v):
        # Map frontend "urgent" -> "high" (entity has no "urgent")
        # Map "sovereign" -> "sovereign" (new highest priority)
        mapping = {"urgent": "high"}
        v = mapping.get(v, v)
        allowed = [p.value for p in TaskPriority]
        if v not in allowed:
            return "normal"
        return v

    @validator("task_type")
    def validate_task_type(cls, v):
        allowed = [t.value for t in TaskType]
        if v not in allowed:
            return "execution"
        return v


class TaskResponse(BaseModel):
    id: str
    agentium_id: Optional[str] = None
    title: str
    description: str
    status: str
    priority: str
    task_type: str = "execution"
    progress: float = 0.0
    assigned_agents: AssignedAgents = AssignedAgents()
    # NEW: Governance fields
    governance: GovernanceInfo = GovernanceInfo()
    # NEW: Error info
    error_info: Optional[ErrorInfo] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    event_count: int = 0

    class Config:
        from_attributes = True
        extra = "allow"


class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    # NEW: Optional note for status changes
    status_note: Optional[str] = Field(None, description="Note explaining status change")
    # NEW: Governance fields
    constitutional_basis: Optional[str] = None
    hierarchical_id: Optional[str] = None
    parent_task_id: Optional[str] = None
    execution_plan_id: Optional[str] = None