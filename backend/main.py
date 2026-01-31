"""
Agentium Main Application
FastAPI backend for AI governance system with hierarchical agents.
"""

import logging
from contextlib import asynccontextmanager
from backend.api.routes import models as model_routes
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from backend.models.database import init_db, get_db, check_health
from backend.models.entities import (
    Agent, Task, Constitution, UserModelConfig,
    AgentHealthReport, ViolationReport
)
from backend.services.model_provider import ModelService
from backend.api.routes import chat as chat_routes
from backend.services.monitoring_service import MonitoringService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan handler.
    Initializes database on startup.
    """
    logger.info("🚀 Starting Agentium...")
    
    # Initialize database (create tables, seed Head of Council)
    try:
        init_db()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("🛑 Shutting down Agentium...")

# Create FastAPI app
app = FastAPI(
    title="Agentium",
    description="AI Agent Governance System with Checks and Balances",
    version="1.0.0",
    lifespan=lifespan
)
app.include_router(model_routes.router)
app.include_router(chat_routes.router)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],  # Frontend dev servers
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ==================== Health & System ====================

@app.get("/health")
async def health_check():
    """System health check."""
    db_health = check_health()
    return {
        "status": "healthy" if db_health["status"] == "healthy" else "degraded",
        "components": {
            "database": db_health,
            "api": "healthy"
        }
    }

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Welcome to Agentium",
        "version": "1.0.0",
        "status": "operational",
        "docs": "/docs"
    }

# ==================== Agent Management ====================

@app.get("/agents")
async def list_agents(
    agent_type: str = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """List all agents with optional filtering."""
    query = db.query(Agent)
    
    if agent_type:
        query = query.filter(Agent.agent_type == agent_type)
    if status:
        query = query.filter(Agent.status == status)
    
    agents = query.all()
    return {
        "count": len(agents),
        "agents": [agent.to_dict() for agent in agents]
    }

@app.get("/agents/{agentium_id}")
async def get_agent(agentium_id: str, db: Session = Depends(get_db)):
    """Get specific agent details."""
    agent = db.query(Agent).filter_by(agentium_id=agentium_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent.to_dict()

@app.post("/agents/{agentium_id}/spawn")
async def spawn_agent(
    agentium_id: str,
    child_type: str,
    name: str,
    db: Session = Depends(get_db)
):
    """
    Spawn a new child agent under parent authority.
    Only allowed for Head of Council and Lead Agents.
    """
    parent = db.query(Agent).filter_by(agentium_id=agentium_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent agent not found")
    
    from backend.models.entities.agents import AgentType
    
    try:
        child_enum = AgentType(child_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid agent type: {child_type}")
    
    try:
        new_agent = parent.spawn_child(child_enum, db, name=name)
        db.commit()
        db.refresh(new_agent)
        
        return {
            "message": "Agent spawned successfully",
            "agent": new_agent.to_dict()
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/agents/{agentium_id}/terminate")
async def terminate_agent(
    agentium_id: str,
    reason: str,
    violation: bool = False,
    db: Session = Depends(get_db)
):
    """Terminate an agent (Head of Council cannot be terminated)."""
    agent = db.query(Agent).filter_by(agentium_id=agentium_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    try:
        agent.terminate(reason, violation)
        db.commit()
        return {
            "message": f"Agent {agentium_id} terminated",
            "reason": reason,
            "violation": violation
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

# ==================== Task Management ====================

@app.post("/tasks")
async def create_task(
    title: str,
    description: str,
    task_type: str = "execution",
    priority: str = "normal",
    db: Session = Depends(get_db)
):
    """Create a new task (submitted by Sovereign/user)."""
    from backend.models.entities.tasks import Task, TaskType, TaskPriority
    
    try:
        task = Task(
            title=title,
            description=description,
            task_type=TaskType(task_type),
            priority=TaskPriority(priority),
            created_by="sovereign"  # TODO: Get from auth
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        
        # Auto-start deliberation if not critical priority
        if task.priority != TaskPriority.CRITICAL:
            # Get active council members
            council = db.query(Agent).filter_by(agent_type="council_member").all()
            if council:
                task.start_deliberation([c.agentium_id for c in council])
                db.commit()
        
        return {
            "message": "Task created",
            "task": task.to_dict()
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/tasks")
async def list_tasks(
    status: str = None,
    agent_id: str = None,
    db: Session = Depends(get_db)
):
    """List tasks with filtering."""
    query = db.query(Task)
    
    if status:
        query = query.filter(Task.status == status)
    if agent_id:
        # Filter by assigned agent
        query = query.filter(
            (Task.lead_agent_id == agent_id) | 
            (Task.assigned_task_agent_ids.contains(agent_id))
        )
    
    tasks = query.order_by(Task.created_at.desc()).all()
    return {
        "count": len(tasks),
        "tasks": [task.to_dict() for task in tasks]
    }

@app.post("/tasks/{task_id}/execute")
async def execute_task(
    task_id: str,
    agent_id: str,
    db: Session = Depends(get_db)
):
    """
    Execute a task using specified agent.
    Uses frontend-configured model settings.
    """
    task = db.query(Task).filter_by(agentium_id=task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    agent = db.query(Agent).filter_by(agentium_id=agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Check if agent can execute this task
    if agent.current_task_id:
        raise HTTPException(status_code=400, detail="Agent is busy with another task")
    
    # Get model configuration
    config = agent.get_model_config(db)
    if not config:
        raise HTTPException(
            status_code=400, 
            detail="No active model configuration found. Please configure in settings."
        )
    
    try:
        # Execute using ModelService
        result = await ModelService.generate_with_agent(
            agent=agent,
            user_message=task.description,
            config_id=config.id
        )
        
        # Update task
        task.complete(
            result_summary=result["content"],
            result_data={"model": result["model"], "tokens": result["tokens_used"]}
        )
        agent.complete_task(success=True)
        
        db.commit()
        
        return {
            "message": "Task executed",
            "result": result["content"],
            "usage": {
                "tokens": result["tokens_used"],
                "latency_ms": result["latency_ms"]
            }
        }
        
    except Exception as e:
        agent.complete_task(success=False)
        task.fail(str(e))
        db.commit()
        raise HTTPException(status_code=500, detail=str(e))

# ==================== Monitoring & Oversight ====================

@app.get("/monitoring/agents/{agentium_id}/health")
async def get_agent_health(
    agentium_id: str,
    db: Session = Depends(get_db)
):
    """Get health reports for a specific agent."""
    agent = db.query(Agent).filter_by(agentium_id=agentium_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Get latest health report
    latest = db.query(AgentHealthReport).filter_by(
        subject_agent_id=agent.id
    ).order_by(AgentHealthReport.created_at.desc()).first()
    
    # Get violation count
    violations = db.query(ViolationReport).filter_by(
        violator_agent_id=agent.id,
        status="open"
    ).count()
    
    return {
        "agent": agentium_id,
        "current_status": agent.status.value,
        "health_score": latest.overall_health_score if latest else 100,
        "latest_report": latest.to_dict() if latest else None,
        "open_violations": violations
    }

@app.post("/monitoring/health-check")
async def conduct_health_check(
    monitor_id: str,
    subject_id: str,
    db: Session = Depends(get_db)
):
    """Manually trigger a health check (monitor evaluates subordinate)."""
    try:
        report = MonitoringService.conduct_health_check(monitor_id, subject_id, db)
        return {
            "message": "Health check completed",
            "report": report.to_dict()
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/monitoring/dashboard/{monitor_id}")
async def get_monitoring_dashboard(
    monitor_id: str,
    db: Session = Depends(get_db)
):
    """Get monitoring dashboard for a specific agent."""
    try:
        dashboard = MonitoringService.get_monitoring_dashboard(monitor_id, db)
        return dashboard
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/monitoring/report-violation")
async def report_violation(
    reporter_id: str,
    violator_id: str,
    severity: str,
    violation_type: str,
    description: str,
    db: Session = Depends(get_db)
):
    """File a violation report against a subordinate."""
    from backend.models.entities.monitoring import ViolationSeverity
    
    try:
        sev_enum = ViolationSeverity(severity)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
    
    try:
        report = MonitoringService.report_violation(
            reporter_id=reporter_id,
            violator_id=violator_id,
            severity=sev_enum,
            violation_type=violation_type,
            description=description,
            evidence=[],  # Would accept file uploads in real implementation
            db=db
        )
        return {
            "message": "Violation reported",
            "report": report.to_dict()
        }
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))

# ==================== Constitution ====================

@app.get("/constitution/current")
async def get_current_constitution(db: Session = Depends(get_db)):
    """Get current active constitution."""
    constitution = db.query(Constitution).filter_by(
        is_active='Y'
    ).order_by(Constitution.effective_date.desc()).first()
    
    if not constitution:
        raise HTTPException(status_code=404, detail="No active constitution found")
    
    return constitution.to_dict()

# ==================== WebSocket for Real-time Updates ====================

class ConnectionManager:
    """Manage WebSocket connections for real-time updates."""
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            await connection.send_json(message)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket for real-time updates.
    Broadcasts: task status changes, agent health alerts, voting updates
    """
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_json()
            # Handle incoming messages (votes, status updates, etc.)
            # Broadcast to all connected clients
            await manager.broadcast(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)