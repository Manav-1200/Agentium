"""
Monitoring API routes.
Provides endpoints for agent monitoring, health checks, and violation reports.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.models.database import get_db
from backend.models.entities.agents import Agent
from backend.models.entities.monitoring import (
    AgentHealthReport, 
    ViolationReport,
    ViolationSeverity
)
from backend.core.auth import get_current_active_user

router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


@router.get("/dashboard/{monitor_id}")
async def get_monitoring_dashboard(
    monitor_id: str,
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get monitoring dashboard data for a specific monitor agent.
    Returns system health, alerts, violations, and agent health reports.
    """
    # Get the monitor agent
    monitor = db.query(Agent).filter(Agent.agentium_id == monitor_id).first()
    
    if not monitor:
        # Return default data if monitor not found
        return {
            "system_health": 100,
            "active_alerts": 0,
            "latest_health_reports": [],
            "recent_violations": []
        }
    
    # Get recent health reports (last 24 hours)
    recent_reports = db.query(AgentHealthReport).filter(
        AgentHealthReport.monitor_agentium_id == monitor_id,
        AgentHealthReport.created_at >= datetime.utcnow() - timedelta(hours=24)
    ).order_by(AgentHealthReport.created_at.desc()).limit(10).all()
    
    # Get recent violations (last 7 days)
    recent_violations = db.query(ViolationReport).filter(
        ViolationReport.created_at >= datetime.utcnow() - timedelta(days=7)
    ).order_by(ViolationReport.created_at.desc()).limit(20).all()
    
    # Calculate system health (average of recent health scores)
    if recent_reports:
        avg_health = sum(r.overall_health_score for r in recent_reports) / len(recent_reports)
        system_health = round(avg_health, 1)
    else:
        system_health = 100.0
    
    # Count active alerts (open violations with high severity)
    active_alerts = db.query(func.count(ViolationReport.id)).filter(
        ViolationReport.status == 'open',
        ViolationReport.severity.in_(['critical', 'major'])
    ).scalar() or 0
    
    # Format health reports for frontend
    health_reports = [
        {
            "id": str(report.id),
            "subject": report.subject_agentium_id,
            "health_score": report.overall_health_score,
            "status": report.status,
            "metrics": {
                "success_rate": report.task_success_rate or 0,
                "tasks_completed": 0,
                "avg_response_time": report.last_response_time_ms or 0
            },
            "created_at": report.created_at.isoformat() if report.created_at else None
        }
        for report in recent_reports
    ]
    
    # Format violations for frontend
    violations = [
        {
            "id": str(v.id),
            "type": v.violation_type,
            "severity": v.severity,
            "violator": v.violator_agentium_id,
            "reporter": v.reporter_agentium_id,
            "description": v.description,
            "status": v.status,
            "created_at": v.created_at.isoformat() if v.created_at else None,
            "resolved_at": None  # ViolationReport has no resolved_at column
        }
        for v in recent_violations
    ]
    
    return {
        "system_health": system_health,
        "active_alerts": active_alerts,
        "latest_health_reports": health_reports,
        "recent_violations": violations,
        "monitor_id": monitor_id,
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get("/agents/{agent_id}/health")
async def get_agent_health(
    agent_id: str,
    days: int = Query(default=7, ge=1, le=30),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get health history for a specific agent.
    """
    agent = db.query(Agent).filter(Agent.agentium_id == agent_id).first()
    
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get health reports for this agent
    reports = db.query(AgentHealthReport).filter(
        AgentHealthReport.subject_agentium_id == agent_id,
        AgentHealthReport.created_at >= datetime.utcnow() - timedelta(days=days)
    ).order_by(AgentHealthReport.created_at.desc()).all()
    
    # Calculate statistics
    if reports:
        avg_health = sum(r.overall_health_score for r in reports) / len(reports)
        min_health = min(r.overall_health_score for r in reports)
        max_health = max(r.overall_health_score for r in reports)
    else:
        avg_health = min_health = max_health = 100.0
    
    return {
        "agent_id": agent_id,
        "agent_name": agent.name,
        "current_health": reports[0].overall_health_score if reports else 100.0,
        "avg_health": round(avg_health, 1),
        "min_health": min_health,
        "max_health": max_health,
        "report_count": len(reports),
        "period_days": days,
        "reports": [
            {
                "id": str(r.id),
                "health_score": r.overall_health_score,
                "status": r.status,
                "metrics": {
                    "success_rate": r.task_success_rate or 0,
                    "avg_response_time": r.last_response_time_ms or 0,
                    "violations": r.constitution_violations_count or 0
                },
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in reports[:50]
        ]
    }


@router.post("/report-violation")
async def report_violation(
    reporter_id: str = Query(..., description="ID of the agent reporting"),
    violator_id: str = Query(..., description="ID of the agent violating"),
    severity: str = Query(..., description="Severity: minor, moderate, major, critical"),
    violation_type: str = Query(..., description="Type of violation"),
    description: str = Query(..., description="Description of the violation"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Report a violation by an agent.
    """
    # Validate agents exist
    reporter = db.query(Agent).filter(Agent.agentium_id == reporter_id).first()
    violator = db.query(Agent).filter(Agent.agentium_id == violator_id).first()
    
    if not reporter:
        raise HTTPException(status_code=404, detail="Reporter agent not found")
    if not violator:
        raise HTTPException(status_code=404, detail="Violator agent not found")
    
    # Validate severity
    try:
        severity_enum = ViolationSeverity(severity.lower())
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid severity. Must be one of: minor, moderate, major, critical"
        )
    
    # Create violation report
    violation = ViolationReport(
        reporter_agentium_id=reporter_id,
        violator_agentium_id=violator_id,
        reporter_agent_id=reporter.id,
        violator_agent_id=violator.id,
        severity=severity,
        violation_type=violation_type,
        description=description,
        status='open',
        created_at=datetime.utcnow()
    )
    
    db.add(violation)
    db.commit()
    db.refresh(violation)
    
    return {
        "success": True,
        "report": {
            "id": str(violation.id),
            "reporter": violation.reporter_agentium_id,
            "violator": violation.violator_agentium_id,
            "severity": violation.severity,
            "type": violation.violation_type,
            "description": violation.description,
            "status": violation.status,
            "created_at": violation.created_at.isoformat()
        }
    }


@router.get("/violations")
async def get_violations(
    status: Optional[str] = Query(None, description="Filter by status: open, resolved, dismissed"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    agent_id: Optional[str] = Query(None, description="Filter by agent (reporter or violator)"),
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get violations with optional filters.
    """
    query = db.query(ViolationReport).filter(
        ViolationReport.created_at >= datetime.utcnow() - timedelta(days=days)
    )
    
    if status:
        query = query.filter(ViolationReport.status == status)
    
    if severity:
        query = query.filter(ViolationReport.severity == severity)
    
    if agent_id:
        query = query.filter(
            (ViolationReport.reporter_agentium_id == agent_id) | 
            (ViolationReport.violator_agentium_id == agent_id)
        )
    
    violations = query.order_by(ViolationReport.created_at.desc()).limit(limit).all()
    
    return {
        "violations": [
            {
                "id": str(v.id),
                "reporter": v.reporter_agentium_id,
                "violator": v.violator_agentium_id,
                "severity": v.severity,
                "type": v.violation_type,
                "description": v.description,
                "status": v.status,
                "created_at": v.created_at.isoformat() if v.created_at else None,
                "resolved_at": None  # No resolved_at column on ViolationReport
            }
            for v in violations
        ],
        "total": len(violations),
        "filters": {
            "status": status,
            "severity": severity,
            "agent_id": agent_id,
            "days": days
        }
    }


@router.patch("/violations/{violation_id}/resolve")
async def resolve_violation(
    violation_id: int,
    resolution_notes: str = Query(..., description="Notes about the resolution"),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Mark a violation as resolved.
    """
    violation = db.query(ViolationReport).filter(ViolationReport.id == violation_id).first()
    
    if not violation:
        raise HTTPException(status_code=404, detail="Violation not found")
    
    if violation.status == 'resolved':
        raise HTTPException(status_code=400, detail="Violation already resolved")
    
    violation.status = 'resolved'
    violation.resolution = resolution_notes  # actual column is 'resolution'
    
    db.commit()
    db.refresh(violation)
    
    return {
        "success": True,
        "violation": {
            "id": str(violation.id),
            "status": violation.status,
            "resolution": violation.resolution
        }
    }


@router.get("/stats")
async def get_monitoring_stats(
    days: int = Query(default=7, ge=1, le=365),
    current_user: dict = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Get overall monitoring statistics.
    """
    start_date = datetime.utcnow() - timedelta(days=days)
    
    # Count violations by severity
    violations_by_severity = {}
    for severity in ['minor', 'moderate', 'major', 'critical']:
        count = db.query(func.count(ViolationReport.id)).filter(
            ViolationReport.severity == severity,
            ViolationReport.created_at >= start_date
        ).scalar() or 0
        violations_by_severity[severity] = count
    
    # Count violations by status
    violations_by_status = {}
    for status in ['open', 'resolved', 'dismissed']:
        count = db.query(func.count(ViolationReport.id)).filter(
            ViolationReport.status == status,
            ViolationReport.created_at >= start_date
        ).scalar() or 0
        violations_by_status[status] = count
    
    # Get agent health average
    avg_health_result = db.query(func.avg(AgentHealthReport.overall_health_score)).filter(
        AgentHealthReport.created_at >= start_date
    ).scalar()
    
    avg_health = round(float(avg_health_result), 1) if avg_health_result else 100.0
    
    # Count total reports
    total_reports = db.query(func.count(AgentHealthReport.id)).filter(
        AgentHealthReport.created_at >= start_date
    ).scalar() or 0
    
    return {
        "period_days": days,
        "violations": {
            "total": sum(violations_by_severity.values()),
            "by_severity": violations_by_severity,
            "by_status": violations_by_status
        },
        "health": {
            "average_score": avg_health,
            "total_reports": total_reports
        },
        "generated_at": datetime.utcnow().isoformat()
    }