"""
Sovereign API Endpoints - Human override control for Head of Council operations.
This gives YOU (the human) visibility and control over the AI agent system.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import asyncio
import json
import psutil  # FIX: added for reliable system metrics (replaces fragile sudo subprocess chain)

from backend.models.database import get_db
from backend.services.host_access import HostAccessService, RestrictedHostAccess
from backend.api.middleware.auth import get_current_user  # Use your existing auth
from backend.models.entities.audit import AuditLog, AuditLevel, AuditCategory
from backend.models.entities.user import User  # Your user model
from pydantic import BaseModel


router = APIRouter(prefix="/sovereign", tags=["sovereign"])

# Pydantic models for requests
class SovereignCommandRequest(BaseModel):
    command: str
    params: dict = {}
    target: str = "head_of_council"
    requireApproval: bool = False
    timeout: int = 300

class BlockAgentRequest(BaseModel):
    reason: str

class WriteFileRequest(BaseModel):
    path: str
    content: str

# Store active WebSocket connections
active_connections: List[WebSocket] = []

async def get_current_sovereign_user(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify that the current user is the Sovereign (admin).
    """
    if not current_user or not current_user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Only the Sovereign can access this endpoint"
        )
    return current_user

@router.get("/system/status")
async def get_system_status(
    current_user: User = Depends(get_current_sovereign_user)
):
    """
    Get real-time host system status (CPU, memory, disk, network).

    FIX: Previously used HostAccessService.execute_command() which prepends
    'sudo -n' to every shell call. Inside Docker, sudo is unavailable, so
    every command returned success=False and all metrics fell back to 0.0.

    Also fixed: the old single-snapshot /proc/stat CPU formula is mathematically
    incorrect — it computes cumulative ticks since boot, not current usage.

    Solution: use psutil directly. It reads kernel data without subprocess or
    sudo and correctly samples CPU usage over a short interval.
    """

    # ── CPU ────────────────────────────────────────────────────────────────────
    # interval=0.5 takes two /proc/stat snapshots 500 ms apart and returns the
    # real delta percentage — the only correct single-call approach.
    cpu_usage: float = psutil.cpu_percent(interval=0.5)
    cpu_cores: int   = psutil.cpu_count(logical=True) or 1
    load_avg: list   = list(psutil.getloadavg()) if hasattr(psutil, "getloadavg") else [0.0, 0.0, 0.0]

    # ── Memory ─────────────────────────────────────────────────────────────────
    # All psutil memory values are in bytes — consistent with the frontend
    # divisor (1_073_741_824 = 1 GiB) to display correct GB values.
    vm              = psutil.virtual_memory()
    mem_total:  int = vm.total
    mem_used:   int = vm.used
    mem_free:   int = vm.available   # "available" is more meaningful than raw "free"
    mem_pct:  float = round(vm.percent, 1)

    # ── Disk ───────────────────────────────────────────────────────────────────
    try:
        disk            = psutil.disk_usage("/")
        disk_total: int = disk.total
        disk_used:  int = disk.used
        disk_free:  int = disk.free
        disk_pct: float = round(disk.percent, 1)
    except Exception:
        disk_total = disk_used = disk_free = 0
        disk_pct = 0.0

    # ── Uptime ─────────────────────────────────────────────────────────────────
    try:
        boot_ts        = psutil.boot_time()
        uptime_seconds = int(datetime.utcnow().timestamp() - boot_ts)
    except Exception:
        uptime_seconds = 0

    hours, remainder  = divmod(uptime_seconds, 3600)
    minutes, _seconds = divmod(remainder, 60)

    # ── Network connections ────────────────────────────────────────────────────
    try:
        net_conns = len(psutil.net_connections())
    except Exception:
        net_conns = 0

    return {
        "cpu": {
            "usage":  round(cpu_usage, 1),
            "cores":  cpu_cores,
            "load":   [round(x, 2) for x in load_avg],
        },
        "memory": {
            "total":      mem_total,
            "used":       mem_used,
            "free":       mem_free,
            "percentage": mem_pct,
        },
        "disk": {
            "total":      disk_total,
            "used":       disk_used,
            "free":       disk_free,
            "percentage": disk_pct,
        },
        "uptime": {
            "seconds":   uptime_seconds,
            "formatted": f"{hours}h {minutes}m",
        },
        "network": {
            "interfaces":  [],
            "connections": net_conns,
        },
        "timestamp": datetime.utcnow().isoformat(),
    }

@router.get("/containers")
async def list_containers(
    current_user: User = Depends(get_current_sovereign_user)
):
    """List all Docker containers (agents) on host system."""
    head = HostAccessService("00001")
    return head.list_containers()

@router.post("/containers/{container_id}/{action}")
async def manage_container(
    container_id: str,
    action: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_sovereign_user)
):
    """Start, stop, restart, or remove agent containers."""
    if action not in ['start', 'stop', 'restart', 'remove']:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    head = HostAccessService("00001")
    
    # Log sovereign intervention
    audit = AuditLog(
        level=AuditLevel.WARNING,
        category=AuditCategory.GOVERNANCE,
        actor_type="sovereign",
        actor_id=current_user.username,
        action=f"container_{action}",
        target_type="container",
        target_id=container_id,
        description=f"Sovereign manually {action}ed container {container_id}",
        after_state={"action": action, "container": container_id},
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    
    result = head.manage_container(action, container_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result

@router.post("/command")
async def execute_sovereign_command(
    command_req: SovereignCommandRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_sovereign_user)
):
    """
    Execute command as Sovereign (human override).
    This bypasses the Head of Council and executes directly on host.
    """
    head = HostAccessService("00001")
    
    # Log the sovereign command
    audit = AuditLog(
        level=AuditLevel.CRITICAL,
        category=AuditCategory.GOVERNANCE,
        actor_type="sovereign",
        actor_id=current_user.username,
        action="sovereign_command",
        target_type="host_system",
        target_id="root",
        description=f"Sovereign executed: {command_req.command}",
        after_state={"command": command_req.command, "params": command_req.params},
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    
    # Execute command
    if command_req.command == "execute":
        result = head.execute_command(
            command_req.params.get("command", []),
            cwd=command_req.params.get("cwd")
        )
    elif command_req.command == "read_file":
        result = head.read_file(command_req.params.get("path", "/"))
    elif command_req.command == "write_file":
        result = head.write_file(
            command_req.params.get("path", "/"),
            command_req.params.get("content", "")
        )
    else:
        raise HTTPException(status_code=400, detail="Unknown command type")
    
    return {
        "id": f"sov_{datetime.utcnow().timestamp()}",
        "agentium_id": "SOVEREIGN",
        "agent_type": "sovereign",
        "action": command_req.command,
        "target": command_req.params.get("path", "host"),
        "status": "completed" if result.get("success") else "failed",
        "result": result,
        "requested_at": datetime.utcnow().isoformat()
    }

@router.get("/audit")
async def get_audit_logs(
    agentium_id: Optional[str] = None,
    level: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_sovereign_user)
):
    """Get detailed audit logs with filtering."""
    query = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    
    if agentium_id:
        query = query.filter(AuditLog.actor_id == agentium_id)
    if level:
        query = query.filter(AuditLog.level == level)
    if start_time:
        query = query.filter(AuditLog.created_at >= start_time)
    if end_time:
        query = query.filter(AuditLog.created_at <= end_time)
    
    logs = query.limit(limit).all()
    return [log.to_dict() for log in logs]

@router.post("/agents/{agentium_id}/block")
async def block_agent(
    agentium_id: str,
    req: BlockAgentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_sovereign_user)
):
    """Emergency block an agent from further actions."""
    audit = AuditLog(
        level=AuditLevel.CRITICAL,
        category=AuditCategory.SECURITY,
        actor_type="sovereign",
        actor_id=current_user.username,
        action="agent_blocked",
        target_type="agent",
        target_id=agentium_id,
        description=f"Agent {agentium_id} blocked by sovereign: {req.reason}",
        after_state={"reason": req.reason, "blocked": True},
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    
    # Notify via WebSocket
    await notify_sovereign({
        "type": "agent_blocked",
        "agentium_id": agentium_id,
        "reason": req.reason,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    return {"status": "blocked", "agentium_id": agentium_id}

@router.post("/agents/{agentium_id}/unblock")
async def unblock_agent(
    agentium_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_sovereign_user)
):
    """Unblock a previously blocked agent."""
    audit = AuditLog(
        level=AuditLevel.INFO,
        category=AuditCategory.SECURITY,
        actor_type="sovereign",
        actor_id=current_user.username,
        action="agent_unblocked",
        target_type="agent",
        target_id=agentium_id,
        description=f"Agent {agentium_id} unblocked by sovereign",
        after_state={"blocked": False},
        is_active=True,
        created_at=datetime.utcnow()
    )
    db.add(audit)
    db.commit()
    
    return {"status": "unblocked", "agentium_id": agentium_id}

@router.get("/files")
async def read_file(
    path: str = Query(...),
    current_user: User = Depends(get_current_sovereign_user)
):
    """Read file from host filesystem."""
    head = HostAccessService("00001")
    return head.read_file(path)

@router.post("/files")
async def write_file(
    req: WriteFileRequest,
    current_user: User = Depends(get_current_sovereign_user)
):
    """Write file to host filesystem (Sovereign only)."""
    head = HostAccessService("00001")
    return head.write_file(req.path, req.content)

@router.get("/directory")
async def list_directory(
    path: str = Query(default="/"),
    current_user: User = Depends(get_current_sovereign_user)
):
    """List directory contents."""
    head = HostAccessService("00001")
    return head.list_directory(path)

@router.websocket("/ws")
async def sovereign_websocket(
    websocket: WebSocket,
    token: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    """WebSocket endpoint for real-time sovereign notifications."""
    
    # Validate token presence
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return
    
    # Validate JWT and check admin privileges
    try:
        from jose import jwt, JWTError
        from backend.core.config import settings
        
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        username = payload.get("sub")
        if not username:
            await websocket.close(code=4001, reason="Invalid token: no subject")
            return
        
        # Verify user exists and is admin
        user = db.query(User).filter(User.username == username).first()
        if not user or not user.is_admin:
            await websocket.close(code=4003, reason="Forbidden: admin access required")
            return
            
    except JWTError as e:
        await websocket.close(code=4001, reason=f"Invalid authentication: {str(e)}")
        return
    except Exception as e:
        await websocket.close(code=1011, reason=f"Authentication error: {str(e)}")
        return
    
    # Accept connection only after successful auth
    await websocket.accept()
    active_connections.append(websocket)
    print(f"[Sovereign WebSocket] ✅ Admin connected: {username}")
    
    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("action") == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
            elif message.get("action") == "subscribe":
                await websocket.send_json({
                    "type": "subscribed",
                    "channel": message.get("channel"),
                    "timestamp": datetime.utcnow().isoformat()
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "content": f"Unknown action: {message.get('action')}",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
    except WebSocketDisconnect:
        print(f"[Sovereign WebSocket] ❌ Disconnected: {username}")
    except json.JSONDecodeError:
        await websocket.send_json({
            "type": "error",
            "content": "Invalid JSON format",
            "timestamp": datetime.utcnow().isoformat()
        })
    except Exception as e:
        print(f"[Sovereign WebSocket] Error: {e}")
        try:
            await websocket.close(code=1011, reason=f"Server error: {str(e)}")
        except:
            pass
    finally:
        if websocket in active_connections:
            active_connections.remove(websocket)

async def notify_sovereign(message: dict):
    """Send notification to all connected sovereign dashboards."""
    disconnected = []
    for conn in active_connections:
        try:
            await conn.send_json(message)
        except:
            disconnected.append(conn)
    
    for conn in disconnected:
        if conn in active_connections:
            active_connections.remove(conn)

# Helper functions — kept for backward compatibility with any other callers
def parse_meminfo(content: str) -> dict:
    """Parse /proc/meminfo output."""
    info = {}
    for line in content.split('\n'):
        if ':' in line:
            key, value = line.split(':', 1)
            # Extract number from string like "16384000 kB"
            num = ''.join(filter(str.isdigit, value))
            info[key.strip()] = int(num) * 1024 if num else 0  # Convert to bytes
    return info

def parse_df(content: str) -> dict:
    """Parse df -B1 output."""
    lines = content.strip().split('\n')
    if len(lines) < 2:
        return {}
    
    parts = lines[1].split()
    if len(parts) < 6:
        return {}
    
    total = int(parts[1])
    used = int(parts[2])
    available = int(parts[3])
    
    return {
        "total": total,
        "used": used,
        "available": available,
        "percentage": round(used / total * 100, 1) if total > 0 else 0
    }

@router.get("/commands")
async def get_command_history(
    limit: int = Query(50, le=1000),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_sovereign_user)
):
    """Get sovereign command history."""
    logs = db.query(AuditLog).filter(
        AuditLog.actor_type == "sovereign",
        AuditLog.action.in_(["sovereign_command", "container_start", "container_stop", "container_restart"])
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    return [log.to_dict() for log in logs]