"""
API routes for ExecutionCheckpoints (Time-Travel and Branching).
Phase 6.5 implementation.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities.checkpoint import ExecutionCheckpoint, CheckpointPhase
from backend.services.checkpoint_service import CheckpointService
from backend.api.schemas.checkpoint import (
    CheckpointCreate,
    CheckpointResponse,
    CheckpointBranchRequest
)
from backend.api.schemas.task import TaskResponse
from pydantic import BaseModel

router = APIRouter(prefix="/checkpoints", tags=["checkpoints"])


# ─── Branch comparison schemas ────────────────────────────────────────────────

class FieldDiff(BaseModel):
    key: str
    left: Any
    right: Any
    status: str  # "added" | "removed" | "changed" | "unchanged"


class AgentStateDiff(BaseModel):
    agent_id: str
    status: str  # "added" | "removed" | "changed" | "unchanged"
    diffs: List[FieldDiff]


class ArtifactDiff(BaseModel):
    key: str
    status: str  # "added" | "removed" | "changed" | "unchanged"
    left: Any
    right: Any


class BranchCompareResponse(BaseModel):
    left_branch: str
    right_branch: str
    left_checkpoint_id: str
    right_checkpoint_id: str
    left_created_at: str
    right_created_at: str
    task_state_diffs: List[FieldDiff]
    agent_state_diffs: List[AgentStateDiff]
    artifact_diffs: List[ArtifactDiff]
    summary: Dict[str, int]  # {"added": n, "removed": n, "changed": n, "unchanged": n}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _diff_dicts(left: Dict[str, Any], right: Dict[str, Any]) -> List[FieldDiff]:
    """Produce a flat list of FieldDiff between two dicts."""
    diffs: List[FieldDiff] = []
    all_keys = set(left.keys()) | set(right.keys())
    for key in sorted(all_keys):
        if key not in left:
            diffs.append(FieldDiff(key=key, left=None, right=right[key], status="added"))
        elif key not in right:
            diffs.append(FieldDiff(key=key, left=left[key], right=None, status="removed"))
        elif left[key] != right[key]:
            diffs.append(FieldDiff(key=key, left=left[key], right=right[key], status="changed"))
        else:
            diffs.append(FieldDiff(key=key, left=left[key], right=right[key], status="unchanged"))
    return diffs


def _summarize(diffs: List[FieldDiff]) -> Dict[str, int]:
    summary: Dict[str, int] = {"added": 0, "removed": 0, "changed": 0, "unchanged": 0}
    for d in diffs:
        summary[d.status] = summary.get(d.status, 0) + 1
    return summary


# ─── Existing routes ──────────────────────────────────────────────────────────

@router.post("", response_model=CheckpointResponse, status_code=status.HTTP_201_CREATED)
def create_checkpoint(
    payload: CheckpointCreate,
    db: Session = Depends(get_db)
):
    """Manually create a checkpoint for a specific task line."""
    try:
        checkpoint = CheckpointService.create_checkpoint(
            db=db,
            task_id=payload.task_id,
            phase=payload.phase,
            actor_id="user_api",
            artifacts=payload.artifacts
        )
        return checkpoint
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("", response_model=List[CheckpointResponse])
def list_checkpoints(
    session_id: Optional[str] = None,
    task_id: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Fetch checkpoints, filterable by session or original task ID."""
    query = db.query(ExecutionCheckpoint).filter(ExecutionCheckpoint.is_active == True)

    if session_id:
        query = query.filter(ExecutionCheckpoint.session_id == session_id)
    if task_id:
        query = query.filter(ExecutionCheckpoint.task_id == task_id)

    return query.order_by(ExecutionCheckpoint.created_at.desc()).limit(limit).all()


@router.get("/{checkpoint_id}", response_model=CheckpointResponse)
def get_checkpoint(checkpoint_id: str, db: Session = Depends(get_db)):
    """Get single checkpoint details."""
    checkpoint = db.query(ExecutionCheckpoint).filter(ExecutionCheckpoint.id == checkpoint_id).first()
    if not checkpoint:
        raise HTTPException(status_code=404, detail="Checkpoint not found")
    return checkpoint


@router.post("/{checkpoint_id}/resume", response_model=TaskResponse)
def resume_from_checkpoint(
    checkpoint_id: str,
    db: Session = Depends(get_db)
):
    """
    Time-travel: Restores the given task back to the target checkpoint.
    """
    try:
        restored_task = CheckpointService.resume_from_checkpoint(
            db=db,
            checkpoint_id=checkpoint_id,
            actor_id="user_api"
        )
        return restored_task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{checkpoint_id}/branch", response_model=TaskResponse)
def branch_from_checkpoint(
    checkpoint_id: str,
    payload: CheckpointBranchRequest,
    db: Session = Depends(get_db)
):
    """
    Branching: Clones the checkpoint into a new separate task tree
    to try an alternative approach.
    """
    try:
        new_task = CheckpointService.branch_from_checkpoint(
            db=db,
            checkpoint_id=checkpoint_id,
            branch_name=payload.branch_name,
            new_supervisor_id=payload.new_supervisor_id,
            actor_id="user_api"
        )
        return new_task
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── NEW: Branch diff ─────────────────────────────────────────────────────────

@router.get("/compare", response_model=BranchCompareResponse)
def compare_branches(
    left_branch: str = Query(..., description="Name of the left/base branch"),
    right_branch: str = Query(..., description="Name of the right/compare branch"),
    task_id: Optional[str] = Query(None, description="Narrow comparison to a specific task"),
    db: Session = Depends(get_db)
):
    """
    Compare two branches by diffing their latest checkpoints.

    Produces structured diffs for:
    - task_state_snapshot (flat key/value)
    - agent_states (per-agent)
    - artifacts (per-artifact key)
    """

    def _latest_for_branch(branch: str) -> ExecutionCheckpoint:
        q = (
            db.query(ExecutionCheckpoint)
            .filter(
                ExecutionCheckpoint.branch_name == branch,
                ExecutionCheckpoint.is_active == True,
            )
        )
        if task_id:
            q = q.filter(ExecutionCheckpoint.task_id == task_id)
        cp = q.order_by(ExecutionCheckpoint.created_at.desc()).first()
        if cp is None:
            raise HTTPException(
                status_code=404,
                detail=f"No active checkpoint found for branch '{branch}'"
                + (f" and task '{task_id}'" if task_id else ""),
            )
        return cp

    left_cp = _latest_for_branch(left_branch)
    right_cp = _latest_for_branch(right_branch)

    # ── task_state_snapshot diff ──────────────────────────────────────────────
    left_state: Dict[str, Any] = left_cp.task_state_snapshot or {}
    right_state: Dict[str, Any] = right_cp.task_state_snapshot or {}
    task_diffs = _diff_dicts(left_state, right_state)

    # ── agent_states diff (per agent) ─────────────────────────────────────────
    left_agents: Dict[str, Any] = left_cp.agent_states or {}
    right_agents: Dict[str, Any] = right_cp.agent_states or {}
    all_agent_ids = set(left_agents.keys()) | set(right_agents.keys())
    agent_diffs: List[AgentStateDiff] = []

    for agent_id in sorted(all_agent_ids):
        l_agent = left_agents.get(agent_id, {}) or {}
        r_agent = right_agents.get(agent_id, {}) or {}

        if agent_id not in left_agents:
            agent_status = "added"
        elif agent_id not in right_agents:
            agent_status = "removed"
        elif l_agent != r_agent:
            agent_status = "changed"
        else:
            agent_status = "unchanged"

        agent_diffs.append(AgentStateDiff(
            agent_id=agent_id,
            status=agent_status,
            diffs=_diff_dicts(l_agent, r_agent),
        ))

    # ── artifacts diff ────────────────────────────────────────────────────────
    left_arts: Dict[str, Any] = left_cp.artifacts or {}
    right_arts: Dict[str, Any] = right_cp.artifacts or {}

    # Normalise: artifacts may be a list of dicts with a "key" field OR a plain dict
    def _normalise_artifacts(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, list):
            out: Dict[str, Any] = {}
            for i, item in enumerate(raw):
                if isinstance(item, dict):
                    k = item.get("key") or item.get("name") or item.get("id") or str(i)
                    out[str(k)] = item
                else:
                    out[str(i)] = item
            return out
        return {}

    left_arts = _normalise_artifacts(left_arts)
    right_arts = _normalise_artifacts(right_arts)
    all_art_keys = set(left_arts.keys()) | set(right_arts.keys())
    artifact_diffs: List[ArtifactDiff] = []

    for key in sorted(all_art_keys):
        if key not in left_arts:
            art_status = "added"
        elif key not in right_arts:
            art_status = "removed"
        elif left_arts[key] != right_arts[key]:
            art_status = "changed"
        else:
            art_status = "unchanged"

        artifact_diffs.append(ArtifactDiff(
            key=key,
            status=art_status,
            left=left_arts.get(key),
            right=right_arts.get(key),
        ))

    # ── summary ───────────────────────────────────────────────────────────────
    all_flat_diffs = task_diffs + [d for a in agent_diffs for d in a.diffs] + [
        FieldDiff(key=a.key, left=a.left, right=a.right, status=a.status)
        for a in artifact_diffs
    ]
    summary = _summarize(all_flat_diffs)

    return BranchCompareResponse(
        left_branch=left_branch,
        right_branch=right_branch,
        left_checkpoint_id=str(left_cp.id),
        right_checkpoint_id=str(right_cp.id),
        left_created_at=left_cp.created_at.isoformat(),
        right_created_at=right_cp.created_at.isoformat(),
        task_state_diffs=task_diffs,
        agent_state_diffs=agent_diffs,
        artifact_diffs=artifact_diffs,
        summary=summary,
    )