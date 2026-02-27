"""
REST API endpoints for skill management.
Supports both User (Sovereign) and Agent authentication.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime

from backend.models.database import get_db
from backend.models.entities.skill import SkillSchema, SkillDB, SkillSubmission
from backend.models.entities.agents import Agent
from backend.models.entities.user import User
from backend.services.skill_manager import skill_manager
from backend.services.skill_rag import skill_rag
from backend.core.auth import get_current_user  # Your actual auth import
from backend.services.auth import get_current_agent as _get_agent_from_service

router = APIRouter(prefix="/skills", tags=["skills"])
security = HTTPBearer(auto_error=False)

async def get_current_user_or_agent(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Unified authentication: accepts either User JWT (from Sovereign) or Agent JWT.
    Returns the user/agent object and metadata.
    """
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Try User authentication first (Sovereign dashboard)
    try:
        # Use your existing get_current_user logic
        from jose import JWTError, jwt
        from backend.core.config import settings
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username: str = payload.get("sub")
        if username:
            user = db.query(User).filter(User.username == username).first()
            if user and user.is_active:
                # Map user role to agent tier
                agent_tier = "head" if user.is_admin else "task_agent"
                return {
                    "type": "user",
                    "user": user,
                    "id": str(user.id),
                    "role": "admin" if user.is_admin else "user",
                    "agent_tier": agent_tier,
                    "is_privileged": user.is_admin,
                    "identifier": user.username
                }
    except Exception:
        pass  # Not a valid user token, try agent token
    
    # Try Agent authentication (Agent system)
    try:
        agent = await _get_agent_from_service(token, db)
        if agent and agent.status == 'active':
            return {
                "type": "agent",
                "agent": agent,
                "id": agent.id,
                "agentium_id": agent.agentium_id,
                "agent_type": agent.agent_type.value,
                "agent_tier": agent.agent_type.value,
                "is_privileged": agent.agent_type.value in ["council", "head"],
                "identifier": agent.agentium_id
            }
    except Exception:
        pass
    
    raise HTTPException(
        status_code=401,
        detail="Invalid token - not a valid User or Agent token",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.get("/search")
async def search_skills(
    query: str = "",
    domain: Optional[str] = None,
    skill_type: Optional[str] = None,
    complexity: Optional[str] = None,
    min_success_rate: float = 0.0,
    n_results: int = 5,
    db: Session = Depends(get_db),
    auth_context: dict = Depends(get_current_user_or_agent)
):
    """
    Search skills with semantic query and filters.
    Works for both Sovereign (User) and Agent authentication.
    """
    filters = {}
    if domain:
        filters["domain"] = domain
    if skill_type:
        filters["skill_type"] = skill_type
    if complexity:
        filters["complexity"] = complexity
    
    results = skill_manager.search_skills(
        query=query,
        agent_tier=auth_context["agent_tier"],
        db=db,
        filters=filters if filters else None,
        n_results=n_results,
        min_success_rate=min_success_rate
    )
    
    return {
        "query": query,
        "results_count": len(results),
        "results": results
    }


@router.get("/stats/popular")
async def get_popular_skills(
    domain: Optional[str] = None,
    limit: int = 10,
    db: Session = Depends(get_db),
    auth_context: dict = Depends(get_current_user_or_agent)
):
    """Get most used skills."""
    query = db.query(SkillDB).filter_by(verification_status="verified")
    if domain:
        query = query.filter_by(domain=domain)
    
    skills = query.order_by(SkillDB.usage_count.desc()).limit(limit).all()
    return {
        "skills": [s.to_dict() for s in skills]
    }


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    auth_context: dict = Depends(get_current_user_or_agent)
):
    """Get full skill details."""
    skill = skill_manager.get_skill_by_id(skill_id, db)
    if not skill:
        raise HTTPException(404, "Skill not found")
    
    # Check access permissions - privileged users/agents can see pending skills
    if skill.verification_status != "verified":
        if not auth_context["is_privileged"]:
            raise HTTPException(403, "Skill pending verification")
    
    return skill.dict()


@router.post("/")
async def create_skill(
    skill_data: dict,
    auto_verify: bool = False,
    db: Session = Depends(get_db),
    auth_context: dict = Depends(get_current_user_or_agent)
):
    """
    Create a new skill.
    Requires Council/Head review unless auto_verify (privileged only).
    """
    # Only privileged users/agents can auto-verify
    if auto_verify and not auth_context["is_privileged"]:
        raise HTTPException(403, "Only Council/Head/Sovereign can auto-verify")
    
    # Get the creator entity (agent or user proxy)
    creator = auth_context.get("agent")
    if not creator and auth_context["type"] == "user":
        # For sovereign users without agent, use head of council as proxy
        creator = db.query(Agent).filter(Agent.agentium_id == "00001").first()
    
    if not creator:
        raise HTTPException(400, "Cannot determine skill creator")
    
    try:
        skill = skill_manager.create_skill(
            skill_data=skill_data,
            creator_agent=creator,
            db=db,
            auto_verify=auto_verify
        )
        return {
            "message": "Skill created successfully",
            "skill_id": skill.skill_id,
            "status": skill.verification_status
        }
    except Exception as e:
        raise HTTPException(400, str(e))


@router.post("/{skill_id}/update")
async def update_skill(
    skill_id: str,
    updates: dict,
    db: Session = Depends(get_db),
    auth_context: dict = Depends(get_current_user_or_agent)
):
    """Create new version of skill."""
    try:
        updater = auth_context.get("agent")
        if not updater and auth_context["type"] == "user":
            updater = db.query(Agent).filter(Agent.agentium_id == "00001").first()
            
        skill = skill_manager.update_skill(
            skill_id=skill_id,
            updates=updates,
            updater_agent=updater,
            db=db
        )
        return {
            "message": "Skill updated",
            "skill_id": skill.skill_id,
            "new_version": skill.version
        }
    except PermissionError as e:
        raise HTTPException(403, str(e))
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.post("/{skill_id}/execute")
async def execute_with_skill(
    skill_id: str,
    task_input: str,
    db: Session = Depends(get_db),
    auth_context: dict = Depends(get_current_user_or_agent)
):
    """Execute task using specific skill."""
    # Verify skill exists and is accessible
    skill = skill_manager.get_skill_by_id(skill_id, db)
    if not skill:
        raise HTTPException(404, "Skill not found")
    
    if skill.verification_status != "verified":
        raise HTTPException(403, "Skill not verified")
    
    # Get agent for execution
    agent = auth_context.get("agent")
    if not agent and auth_context["type"] == "user":
        # For sovereign users, use head of council as proxy
        agent = db.query(Agent).filter(Agent.agentium_id == "00001").first()
    
    if not agent:
        raise HTTPException(403, "Execution requires agent context")
    
    result = await skill_rag.execute_with_skills(
        task_description=task_input,
        agent=agent,
        db=db
    )
    
    return result


@router.get("/submissions/pending")
async def get_pending_submissions(
    db: Session = Depends(get_db),
    auth_context: dict = Depends(get_current_user_or_agent)
):
    """Get skill submissions pending review (privileged only)."""
    if not auth_context["is_privileged"]:
        raise HTTPException(403, "Council/Head/Sovereign only")
    
    submissions = db.query(SkillSubmission).filter_by(status="pending").all()
    return {
        "count": len(submissions),
        "submissions": [
            {
                "submission_id": s.submission_id,
                "skill_id": s.skill_id,
                "submitted_by": s.submitted_by,
                "submitted_at": s.submitted_at.isoformat() if s.submitted_at else None,
                "skill_data": s.skill_data
            }
            for s in submissions
        ]
    }


@router.post("/submissions/{submission_id}/review")
async def review_submission(
    submission_id: str,
    decision: str,  # approve, reject
    notes: Optional[str] = None,
    db: Session = Depends(get_db),
    auth_context: dict = Depends(get_current_user_or_agent)
):
    """Review skill submission (privileged only)."""
    if not auth_context["is_privileged"]:
        raise HTTPException(403, "Council/Head/Sovereign only")
    
    submission = db.query(SkillSubmission).filter_by(submission_id=submission_id).first()
    if not submission:
        raise HTTPException(404, "Submission not found")
    
    # Update skill status
    skill_db = db.query(SkillDB).filter_by(skill_id=submission.skill_id).first()
    if not skill_db:
        raise HTTPException(404, "Skill not found")
    
    reviewer_id = auth_context.get("agentium_id") or auth_context.get("identifier") or "unknown"
    
    if decision == "approve":
        skill_db.verification_status = "verified"
        skill_db.verified_by = reviewer_id
        skill_db.verified_at = datetime.utcnow()
        submission.status = "approved"
    else:
        skill_db.verification_status = "rejected"
        skill_db.rejection_reason = notes or "Rejected"
        submission.status = "rejected"
    
    submission.reviewed_by = reviewer_id
    submission.reviewed_at = datetime.utcnow()
    submission.review_notes = notes
    
    db.commit()
    
    return {
        "message": f"Submission {decision}ed",
        "skill_id": submission.skill_id
    }