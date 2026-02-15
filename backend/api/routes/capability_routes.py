"""
API routes for Capability Management.
Provides endpoints for capability inspection, granting, and revocation.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities.agents import Agent
from backend.services.capability_registry import (
    CapabilityRegistry, 
    Capability, 
    capability_registry
)
from backend.core.auth import get_current_active_user

router = APIRouter(prefix="/api/v1/capabilities", tags=["Capabilities"])


# ═══════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════

class CapabilityCheckRequest(BaseModel):
    agentium_id: str = Field(..., description="Agent ID to check")
    capability: str = Field(..., description="Capability name to verify")


class CapabilityCheckResponse(BaseModel):
    has_capability: bool
    agentium_id: str
    capability: str
    tier: str
    reason: Optional[str] = None


class GrantCapabilityRequest(BaseModel):
    target_agentium_id: str = Field(..., description="Agent to grant capability to")
    capability: str = Field(..., description="Capability to grant")
    reason: str = Field(..., min_length=10, description="Justification for granting")


class RevokeCapabilityRequest(BaseModel):
    target_agentium_id: str = Field(..., description="Agent to revoke capability from")
    capability: str = Field(..., description="Capability to revoke")
    reason: str = Field(..., min_length=10, description="Justification for revocation")


class CapabilityProfileResponse(BaseModel):
    tier: str
    agentium_id: str
    base_capabilities: List[str]
    granted_capabilities: List[str]
    revoked_capabilities: List[str]
    effective_capabilities: List[str]
    total_count: int


class CapabilityAuditResponse(BaseModel):
    total_agents: int
    tier_distribution: dict
    dynamic_grants_total: int
    dynamic_revocations_total: int
    recent_capability_changes: List[dict]


# ═══════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════

@router.get("/list")
async def list_all_capabilities(
    current_user: dict = Depends(get_current_active_user)
):
    """
    List all available capabilities in the system.
    """
    capabilities = {
        "head_of_council_0xxxx": [cap.value for cap in Capability if cap.value in [
            "veto", "amend_constitution", "liquidate_any", "admin_vector_db",
            "override_budget", "emergency_shutdown", "grant_capability", "revoke_capability"
        ]],
        "council_members_1xxxx": [cap.value for cap in Capability if cap.value in [
            "propose_amendment", "allocate_resources", "audit_system", "moderate_knowledge",
            "spawn_lead", "vote_on_amendment", "review_violations", "manage_channels"
        ]],
        "lead_agents_2xxxx": [cap.value for cap in Capability if cap.value in [
            "spawn_task_agent", "delegate_work", "request_resources", "submit_knowledge",
            "liquidate_task_agent", "escalate_to_council"
        ]],
        "task_agents_3xxxx": [cap.value for cap in Capability if cap.value in [
            "execute_task", "report_status", "escalate_blocker", "query_knowledge",
            "use_tools", "request_clarification"
        ]]
    }
    
    return {
        "capabilities_by_tier": capabilities,
        "total_capabilities": len(Capability),
        "all_capabilities": [cap.value for cap in Capability]
    }


@router.post("/check", response_model=CapabilityCheckResponse)
async def check_capability(
    request: CapabilityCheckRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Check if a specific agent has a specific capability.
    """
    # Get agent
    agent = db.query(Agent).filter_by(agentium_id=request.agentium_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {request.agentium_id} not found"
        )
    
    # Validate capability
    try:
        capability = Capability(request.capability)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid capability: {request.capability}"
        )
    
    # Check capability
    has_capability = CapabilityRegistry.can_agent(agent, capability, db)
    tier = CapabilityRegistry.get_agent_tier(agent.agentium_id)
    
    return CapabilityCheckResponse(
        has_capability=has_capability,
        agentium_id=request.agentium_id,
        capability=request.capability,
        tier=tier,
        reason="Capability granted" if has_capability else f"Requires tier {CapabilityRegistry._get_required_tier(capability)}"
    )


@router.get("/agent/{agentium_id}", response_model=CapabilityProfileResponse)
async def get_agent_capabilities(
    agentium_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get complete capability profile for an agent.
    """
    agent = db.query(Agent).filter_by(agentium_id=agentium_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agentium_id} not found"
        )
    
    profile = CapabilityRegistry.get_agent_capabilities(agent)
    
    return CapabilityProfileResponse(**profile)


@router.post("/grant")
async def grant_capability(
    request: GrantCapabilityRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Grant a capability to an agent.
    Requires GRANT_CAPABILITY permission.
    """
    # Get target agent
    target_agent = db.query(Agent).filter_by(agentium_id=request.target_agentium_id).first()
    
    if not target_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target agent {request.target_agentium_id} not found"
        )
    
    # Get granting agent (user's Head of Council or own agent)
    # For now, assume user is sovereign and use Head 00001
    granter = db.query(Agent).filter_by(agentium_id="00001").first()
    
    if not granter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Head of Council not found (required to grant capabilities)"
        )
    
    # Validate capability
    try:
        capability = Capability(request.capability)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid capability: {request.capability}"
        )
    
    # Grant the capability
    try:
        success = CapabilityRegistry.grant_capability(
            target_agent,
            capability,
            granter,
            request.reason,
            db
        )
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Capability '{request.capability}' granted to {request.target_agentium_id}",
            "target_agentium_id": request.target_agentium_id,
            "capability": request.capability,
            "granted_by": granter.agentium_id,
            "reason": request.reason
        }
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to grant capability: {str(e)}"
        )


@router.post("/revoke")
async def revoke_capability(
    request: RevokeCapabilityRequest,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Revoke a capability from an agent.
    Requires REVOKE_CAPABILITY permission.
    """
    # Get target agent
    target_agent = db.query(Agent).filter_by(agentium_id=request.target_agentium_id).first()
    
    if not target_agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target agent {request.target_agentium_id} not found"
        )
    
    # Get revoking agent (use Head 00001)
    revoker = db.query(Agent).filter_by(agentium_id="00001").first()
    
    if not revoker:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Head of Council not found (required to revoke capabilities)"
        )
    
    # Validate capability
    try:
        capability = Capability(request.capability)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid capability: {request.capability}"
        )
    
    # Revoke the capability
    try:
        success = CapabilityRegistry.revoke_capability(
            target_agent,
            capability,
            revoker,
            request.reason,
            db
        )
        
        db.commit()
        
        return {
            "success": True,
            "message": f"Capability '{request.capability}' revoked from {request.target_agentium_id}",
            "target_agentium_id": request.target_agentium_id,
            "capability": request.capability,
            "revoked_by": revoker.agentium_id,
            "reason": request.reason
        }
        
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e)
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke capability: {str(e)}"
        )


@router.get("/audit", response_model=CapabilityAuditResponse)
async def capability_audit(
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Generate system-wide capability audit report.
    Admin/Council only.
    """
    # Check if user is admin
    if not current_user.get("is_admin") and current_user.get("role") != "sovereign":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Sovereign privileges required"
        )
    
    report = CapabilityRegistry.capability_audit_report(db)
    
    return CapabilityAuditResponse(**report)


@router.delete("/agent/{agentium_id}/all")
async def revoke_all_capabilities(
    agentium_id: str,
    reason: str = "manual_revocation",
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Revoke ALL capabilities from an agent.
    Emergency use only. Requires admin/sovereign privileges.
    """
    # Check if user is admin
    if not current_user.get("is_admin") and current_user.get("role") != "sovereign":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin or Sovereign privileges required"
        )
    
    # Get agent
    agent = db.query(Agent).filter_by(agentium_id=agentium_id).first()
    
    if not agent:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent {agentium_id} not found"
        )
    
    # Protection: Cannot revoke all capabilities from Head 00001
    if agentium_id == "00001":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot revoke all capabilities from Head of Council"
        )
    
    try:
        CapabilityRegistry.revoke_all_capabilities(agent, reason, db)
        db.commit()
        
        return {
            "success": True,
            "message": f"All capabilities revoked from {agentium_id}",
            "agentium_id": agentium_id,
            "reason": reason
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke capabilities: {str(e)}"
        )
        