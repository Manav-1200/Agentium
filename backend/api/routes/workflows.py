"""
Workflow execution API routes.

  POST /api/v1/workflows/execute       — parse + execute a multi-step workflow
  GET  /api/v1/workflows/{workflow_id} — live status + sub-task details
  GET  /api/v1/workflows/              — paginated list of recent workflows
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities.workflow import WorkflowExecution
from backend.core.auth import get_current_active_user

router = APIRouter(tags=["Workflows"])


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response schemas
# ─────────────────────────────────────────────────────────────────────────────

class WorkflowExecuteRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=3,
        description=(
            "Compound user instruction, e.g. "
            "'Find HDFC price, email my broker, and remind me in 2 weeks.'"
        ),
    )
    model_config_id: Optional[str] = Field(
        None,
        description="LLM config ID to use for intent decomposition (optional).",
    )


class WorkflowExecuteResponse(BaseModel):
    workflow_id: str
    status: str
    subtask_count: int
    detail: str


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/workflows/execute", response_model=WorkflowExecuteResponse)
async def execute_workflow(
    request: WorkflowExecuteRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """
    Parse a compound instruction into atomic sub-tasks and execute them.

    Immediate tasks run synchronously in dependency order; deferred tasks
    (e.g. 2-week follow-up) are scheduled via Celery and return a
    ``scheduled`` status.
    """
    from backend.services.workflow_planner import WorkflowPlanner
    from backend.services.workflow_executor import WorkflowExecutor

    planner = WorkflowPlanner(model_config_id=request.model_config_id)
    plan = await planner.parse(request.message)

    executor = WorkflowExecutor()
    execution = await executor.execute(
        plan,
        created_by=current_user.get("agentium_id") or current_user.get("username"),
    )

    return WorkflowExecuteResponse(
        workflow_id=execution.workflow_id,
        status=execution.status,
        subtask_count=len(plan.subtasks),
        detail=(
            f"Workflow executed with {len(plan.subtasks)} sub-task(s). "
            f"Final status: {execution.status}."
        ),
    )


@router.get("/workflows/", summary="List recent workflows")
def list_workflows(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return a paginated list of WorkflowExecution records (newest first)."""
    total = db.query(WorkflowExecution).count()
    rows = (
        db.query(WorkflowExecution)
        .order_by(WorkflowExecution.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "workflows": [wf.to_dict() for wf in rows],
    }


@router.get("/workflows/{workflow_id}", summary="Get workflow status")
def get_workflow(
    workflow_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    """Return the full WorkflowExecution record, including all sub-tasks."""
    wf = db.query(WorkflowExecution).filter_by(workflow_id=workflow_id).first()
    if not wf:
        raise HTTPException(
            status_code=404,
            detail=f"Workflow '{workflow_id}' not found.",
        )
    return wf.to_dict()