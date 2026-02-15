"""
API routes for Agent Lifecycle Management.
Provides endpoints for spawning, promoting, and liquidating agents.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities.agents import Agent
from backend.services.reincarnation_service import reincarnation_service
from backend.core.auth import get_current_active_user

router = APIRouter(prefix="/api/v1/agents/lifecycle", tags=["Agent Lifecycle"])


# ═══════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════

class SpawnTaskAgentRequest(BaseModel):
    parent_agentium_id: str = Field(..., description="Parent agent ID (Lead or Council)")
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=500)
    capabilities: Optional[List[str]] = Field(default=None, description="Custom capabilities to grant")


class SpawnLeadAgentRequest(BaseModel):
    parent_agentium_id: str = Field(..., description="Parent agent ID (Council or Head)")
    name: str = Field(..., min_length=3, max_length=100)
    description: str = Field(..., min_length=10, max_length=500)


class PromoteAgentRequest(BaseModel):
    task_agentium_id: str = Field(..., description="Task Agent ID to promote (3xxxx)")
    promoted_by_agentium_id: str = Field(..., description="Agent authorizing promotion (Council/Head)")
    reason: str = Field(..., min_length=20, max_length=500, description="Justification for promotion")


class LiquidateAgentRequest(BaseModel):
    target_agentium_id: str = Field(..., description="Agent ID to liquidate")
    liquidated_by_agentium_id: str = Field(..., description="Agent authorizing liquidation")
    reason: str = Field(..., min_length=20, max_length=500, description="Justification for liquidation")
    force: bool = Field(default=False, description="Force liquidation (bypass safety checks)")


class AgentSpawnResponse(BaseModel):
    success: bool
    agentium_id: str
    name: str
    agent_type: str
    parent_agentium_id: str
    capabilities: List[str]
    message: str


class PromotionResponse(BaseModel):
    success: bool
    old_agentium_id: str
    new_agentium_id: str
    promoted_by: str
    reason: str
    tasks_transferred: int
    message: str


class LiquidationResponse(BaseModel):
    success: bool
    agentium_id: str
    liquidated_by: str
    reason: str
    tasks_cancelled: int
    tasks_reassigned: int
    child_agents_notified: int
    capabilities_revoked: int
    message: str


class CapacityResponse(BaseModel):
    head: dict
    council: dict
    lead: dict
    task: dict
    warnings: List[str]


# ═══════════════════════════════════════════════════════════
# SPAWNING ENDPOINTS
# ═══════════════════════════════════════════════════════════

@router.post("/spawn/task", response_model=AgentSpawnResponse)
async def spawn_task_agent(
    request: SpawnTaskAgentRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Spawn a new Task Agent (3xxxx).
    Parent must be a Lead Agent or Council Member.
    """
    # Get parent agent
    parent = db.query(Agent).filter_by(agentium_id=request.parent_agentium_id).first()
    
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent agent {request.parent_agentium_id} not found"
        )
    
    # Verify parent is Lead (2xxxx) or Council (1xxxx)
    if not request.parent_agentium_id.startswith(('1', '2')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent must be a Lead Agent (2xxxx) or Council Member (1xxxx)"
        )
    
    try:
        # Spawn the Task Agent
        task_agent = reincarnation_service.spawn_task_agent(
            parent=parent,
            name=request.name,
            description=request.description,
            capabilities=request.capabilities,
            db=db
        )
        
        db.commit()
        
        # Get effective capabilities
        from backend.services.capability_registry import CapabilityRegistry
        caps_profile = CapabilityRegistry.get_agent_capabilities(task_agent)
        
        return AgentSpawnResponse(
            success=True,
            agentium_id=task_agent.agentium_id,
            name=task_agent.name,
            agent_type="task",
            parent_agentium_id=request.parent_agentium_id,
            capabilities=caps_profile["effective_capabilities"],
            message=f"Task Agent {task_agent.agentium_id} spawned successfully"
        )
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to spawn Task Agent: {str(e)}"
        )


@router.post("/spawn/lead", response_model=AgentSpawnResponse)
async def spawn_lead_agent(
    request: SpawnLeadAgentRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Spawn a new Lead Agent (2xxxx).
    Parent must be a Council Member or Head of Council.
    """
    # Get parent agent
    parent = db.query(Agent).filter_by(agentium_id=request.parent_agentium_id).first()
    
    if not parent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Parent agent {request.parent_agentium_id} not found"
        )
    
    # Verify parent is Council (1xxxx) or Head (0xxxx)
    if not request.parent_agentium_id.startswith(('0', '1')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parent must be a Council Member (1xxxx) or Head of Council (0xxxx)"
        )
    
    try:
        # Spawn the Lead Agent
        lead_agent = reincarnation_service.spawn_lead_agent(
            parent=parent,
            name=request.name,
            description=request.description,
            db=db
        )
        
        db.commit()
        
        # Get effective capabilities
        from backend.services.capability_registry import CapabilityRegistry
        caps_profile = CapabilityRegistry.get_agent_capabilities(lead_agent)
        
        return AgentSpawnResponse(
            success=True,
            agentium_id=lead_agent.agentium_id,
            name=lead_agent.name,
            agent_type="lead",
            parent_agentium_id=request.parent_agentium_id,
            capabilities=caps_profile["effective_capabilities"],
            message=f"Lead Agent {lead_agent.agentium_id} spawned successfully"
        )
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to spawn Lead Agent: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════
# PROMOTION ENDPOINT
# ═══════════════════════════════════════════════════════════

@router.post("/promote", response_model=PromotionResponse)
async def promote_task_to_lead(
    request: PromoteAgentRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Promote a Task Agent (3xxxx) to Lead Agent (2xxxx).
    Requires Council or Head authorization.
    """
    # Get promoter agent
    promoter = db.query(Agent).filter_by(agentium_id=request.promoted_by_agentium_id).first()
    
    if not promoter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Promoter agent {request.promoted_by_agentium_id} not found"
        )
    
    # Verify task agent exists
    if not request.task_agentium_id.startswith('3'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only Task Agents (3xxxx) can be promoted to Lead"
        )
    
    try:
        # Execute promotion
        lead_agent = reincarnation_service.promote_to_lead(
            agent_id=request.task_agentium_id,
            promoted_by=promoter,
            reason=request.reason,
            db=db
        )
        
        # Get tasks transferred count from audit
        from backend.models.entities.audit import AuditLog
        promotion_audit = db.query(AuditLog).filter_by(
            action="agent_promoted",
            target_id=lead_agent.agentium_id
        ).order_by(AuditLog.created_at.desc()).first()
        
        tasks_transferred = 0
        if promotion_audit and promotion_audit.meta_data:
            tasks_transferred = promotion_audit.meta_data.get("tasks_transferred", 0)
        
        return PromotionResponse(
            success=True,
            old_agentium_id=request.task_agentium_id,
            new_agentium_id=lead_agent.agentium_id,
            promoted_by=request.promoted_by_agentium_id,
            reason=request.reason,
            tasks_transferred=tasks_transferred,
            message=f"Agent {request.task_agentium_id} promoted to {lead_agent.agentium_id}"
        )
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to promote agent: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════
# LIQUIDATION ENDPOINT
# ═══════════════════════════════════════════════════════════

@router.post("/liquidate", response_model=LiquidationResponse)
async def liquidate_agent(
    request: LiquidateAgentRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Liquidate (terminate) an agent with full cleanup.
    Requires appropriate authorization based on tier hierarchy.
    """
    # Get liquidator agent
    liquidator = db.query(Agent).filter_by(agentium_id=request.liquidated_by_agentium_id).first()
    
    if not liquidator:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Liquidator agent {request.liquidated_by_agentium_id} not found"
        )
    
    # Protection: Cannot liquidate Head 00001
    if request.target_agentium_id == "00001" and not request.force:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot liquidate Head of Council (00001)"
        )
    
    try:
        # Execute liquidation
        summary = reincarnation_service.liquidate_agent(
            agent_id=request.target_agentium_id,
            liquidated_by=liquidator,
            reason=request.reason,
            db=db,
            force=request.force
        )
        
        return LiquidationResponse(
            success=True,
            agentium_id=summary["agent_id"],
            liquidated_by=summary["liquidated_by"],
            reason=summary["reason"],
            tasks_cancelled=summary["tasks_cancelled"],
            tasks_reassigned=summary["tasks_reassigned"],
            child_agents_notified=summary["child_agents_notified"],
            capabilities_revoked=summary["capabilities_revoked"],
            message=f"Agent {request.target_agentium_id} liquidated successfully"
        )
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to liquidate agent: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════
# CAPACITY MANAGEMENT ENDPOINT
# ═══════════════════════════════════════════════════════════

@router.get("/capacity", response_model=CapacityResponse)
async def get_capacity(
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get available ID pool capacity for each agent tier.
    Shows warnings for tiers approaching capacity limits.
    """
    capacity = reincarnation_service.get_available_capacity(db)
    
    # Generate warnings
    warnings = []
    for tier_name, tier_data in capacity.items():
        if tier_data["critical"]:
            warnings.append(f"CRITICAL: {tier_name.upper()} tier at {tier_data['percentage']}% capacity")
        elif tier_data["warning"]:
            warnings.append(f"WARNING: {tier_name.upper()} tier at {tier_data['percentage']}% capacity")
    
    return CapacityResponse(
        head=capacity["head"],
        council=capacity["council"],
        lead=capacity["lead"],
        task=capacity["task"],
        warnings=warnings
    )


# ═══════════════════════════════════════════════════════════
# BULK OPERATIONS
# ═══════════════════════════════════════════════════════════

@router.post("/bulk/liquidate-idle")
async def bulk_liquidate_idle_agents(
    idle_days_threshold: int = 7,
    dry_run: bool = True,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Bulk liquidate idle agents.
    Set dry_run=false to actually execute.
    Admin/Sovereign only.
    """
    # Check permissions
    if not current_user.get("is_admin") and current_user.get("role") != "sovereign":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Sovereign privileges required"
        )
    
    # Use the enhanced idle governance auto-liquidation
    from backend.services.idle_governance_enhanced import enhanced_idle_governance
    from datetime import timedelta
    
    # Temporarily adjust threshold
    original_threshold = enhanced_idle_governance.IDLE_THRESHOLD_DAYS
    enhanced_idle_governance.IDLE_THRESHOLD_DAYS = idle_days_threshold
    
    try:
        if dry_run:
            # Just detect, don't liquidate
            idle_agents = await enhanced_idle_governance.detect_idle_agents(db)
            
            return {
                "dry_run": True,
                "idle_agents_found": len(idle_agents),
                "idle_agents": idle_agents,
                "message": "Dry run complete. Set dry_run=false to execute liquidation."
            }
        else:
            # Actually liquidate
            summary = await enhanced_idle_governance.auto_liquidate_expired(db)
            
            return {
                "dry_run": False,
                "liquidated_count": summary["liquidated_count"],
                "liquidated": summary["liquidated"],
                "skipped_count": summary["skipped_count"],
                "skipped": summary["skipped"],
                "message": f"Liquidated {summary['liquidated_count']} idle agents"
            }
            
    finally:
        # Restore original threshold
        enhanced_idle_governance.IDLE_THRESHOLD_DAYS = original_threshold


@router.get("/stats/lifecycle")
async def get_lifecycle_stats(
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get comprehensive lifecycle statistics.
    """
    from backend.models.entities.audit import AuditLog
    from datetime import timedelta
    
    # Count lifecycle events from audit log (last 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    spawned = db.query(AuditLog).filter(
        AuditLog.action.in_(["agent_spawned", "lead_spawned"]),
        AuditLog.created_at >= thirty_days_ago
    ).count()
    
    promoted = db.query(AuditLog).filter(
        AuditLog.action == "agent_promoted",
        AuditLog.created_at >= thirty_days_ago
    ).count()
    
    liquidated = db.query(AuditLog).filter(
        AuditLog.action == "agent_liquidated",
        AuditLog.created_at >= thirty_days_ago
    ).count()
    
    reincarnated = db.query(AuditLog).filter(
        AuditLog.action == "agent_birth",
        AuditLog.created_at >= thirty_days_ago
    ).count()
    
    # Get current active agents by tier
    from sqlalchemy import func
    active_by_tier = {}
    for prefix in ['0', '1', '2', '3']:
        count = db.query(func.count(Agent.id)).filter(
            Agent.agentium_id.like(f"{prefix}%"),
            Agent.is_active == 'Y'
        ).scalar()
        active_by_tier[f"tier_{prefix}"] = count
    
    return {
        "period_days": 30,
        "lifecycle_events": {
            "spawned": spawned,
            "promoted": promoted,
            "liquidated": liquidated,
            "reincarnated": reincarnated
        },
        "active_agents_by_tier": active_by_tier,
        "capacity": reincarnation_service.get_available_capacity(db)
    }