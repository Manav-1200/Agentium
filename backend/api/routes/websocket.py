"""
WebSocket endpoint for real-time chat with authentication.
User must authenticate BEFORE or DURING connection.
"""

import json
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status, Query
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities import Agent, HeadOfCouncil
from backend.services.chat_service import ChatService
from backend.core.config import settings
from backend.core.auth import get_current_active_user  # ✅ Import at top

router = APIRouter()


class ConnectionManager:
    """Manage authenticated WebSocket connections with heartbeat support."""
    
    def __init__(self):
        # Map: websocket -> user_info
        self.active_connections: Dict[WebSocket, Dict[str, Any]] = {}
        # Map: user_id -> websocket (for direct messaging)
        self.user_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, websocket: WebSocket, token: str, db: Session) -> Optional[Dict[str, Any]]:
        """
        Authenticate connection BEFORE accepting.
        Returns user info if successful, None if authentication fails.
        """
        try:
            # Verify JWT token
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
            username = payload.get("sub")
            
            if not username:
                await websocket.close(code=4001, reason="Invalid token: no subject")
                return None
            
            # Check if Head of Council exists
            head = db.query(HeadOfCouncil).filter_by(agentium_id="00001").first()
            if not head:
                await websocket.close(code=1011, reason="System not initialized - no Head of Council")
                return None
            
            # Accept connection ONLY after successful authentication
            await websocket.accept()
            
            # Store connection info
            user_info = {
                "username": username,
                "role": payload.get("role", "sovereign"),
                "user_id": payload.get("user_id"),
                "head_agent_id": head.id,
                "head_agentium_id": head.agentium_id
            }
            
            self.active_connections[websocket] = user_info
            self.user_connections[username] = websocket
            
            print(f"[WebSocket] ✅ Authenticated: {username} ({datetime.utcnow().isoformat()})")
            return user_info
            
        except JWTError as e:
            # Reject connection - invalid token
            await websocket.close(code=4001, reason=f"Invalid authentication: {str(e)}")
            return None
        except Exception as e:
            # Reject connection - other error
            await websocket.close(code=1011, reason=f"Authentication error: {str(e)}")
            return None
    
    def disconnect(self, websocket: WebSocket) -> Optional[str]:
        """Remove connection and return username if found."""
        username = None
        if websocket in self.active_connections:
            user_info = self.active_connections[websocket]
            username = user_info.get("username")
            if username and username in self.user_connections:
                del self.user_connections[username]
            del self.active_connections[websocket]
            print(f"[WebSocket] ❌ Disconnected: {username}")
        return username
    
    async def send_personal_message(self, message: dict, username: str) -> bool:
        """Send JSON message to specific user."""
        if username in self.user_connections:
            websocket = self.user_connections[username]
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                print(f"[WebSocket] Error sending to {username}: {e}")
                return False
        return False
    
    async def broadcast(self, message: dict, exclude: Optional[WebSocket] = None):
        """Broadcast JSON message to all authenticated connections."""
        disconnected = []
        for connection, user_info in self.active_connections.items():
            if connection == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                print(f"[WebSocket] Broadcast error to {user_info.get('username')}: {e}")
                disconnected.append(connection)
        
        # Clean up failed connections
        for conn in disconnected:
            self.disconnect(conn)
    
    def get_connection_count(self) -> int:
        """Return number of active connections."""
        return len(self.active_connections)


# Global connection manager instance
manager = ConnectionManager()


@router.websocket("/ws/chat")
async def websocket_chat_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT access token"),
    db: Session = Depends(get_db)
):
    """
    Authenticated WebSocket endpoint for Sovereign ↔ Head of Council chat.
    
    Connection flow:
    1. Client connects with ?token=JWT in URL
    2. Server validates JWT BEFORE accepting (4001 if invalid)
    3. If valid: connection accepted, welcome message sent
    4. Messages processed through ChatService
    
    Heartbeat: Client should send {"type": "ping"} every 30s
    """
    
    # Validate token exists
    if not token:
        await websocket.close(code=4001, reason="Token required - provide ?token=JWT")
        return
    
    # Attempt authentication (connection accepted here on success)
    user_info = await manager.connect(websocket, token, db)
    
    if not user_info:
        # Authentication failed - connection already closed
        return
    
    # Send initial messages
    try:
        # Welcome message
        await websocket.send_json({
            "type": "system",
            "role": "system",
            "content": f"Welcome {user_info['username']}. Connected to Head of Council ({user_info['head_agentium_id']}).",
            "timestamp": datetime.utcnow().isoformat(),
            "metadata": {
                "agent_id": user_info['head_agentium_id'],
                "connection_id": id(websocket)
            }
        })
        
        # Ready status
        await websocket.send_json({
            "type": "status",
            "role": "head_of_council",
            "content": "Head of Council is ready to receive commands.",
            "agent_id": user_info['head_agentium_id'],
            "timestamp": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        print(f"[WebSocket] Error sending welcome: {e}")
        manager.disconnect(websocket)
        return
    
    # Main message handling loop
    try:
        while True:
            # Receive message from client (Sovereign)
            data = await websocket.receive_text()
            
            # Parse message
            try:
                message_data = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "content": "Invalid JSON format",
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue
            
            message_type = message_data.get("type", "message")
            
            # Handle ping/pong heartbeat
            if message_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue
            
            # Handle chat messages
            if message_type == "message":
                content = message_data.get("content", "").strip()
                
                if not content:
                    await websocket.send_json({
                        "type": "error",
                        "content": "Empty message content",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    continue
                
                # Acknowledge receipt
                await websocket.send_json({
                    "type": "status",
                    "role": "system",
                    "content": "Processing your command...",
                    "timestamp": datetime.utcnow().isoformat()
                })
                
                try:
                    # Get fresh Head of Council instance
                    head = db.query(HeadOfCouncil).filter_by(
                        id=user_info["head_agent_id"]
                    ).first()
                    
                    if not head:
                        await websocket.send_json({
                            "type": "error",
                            "content": "Head of Council not available",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                        continue
                    
                    # Process message through ChatService
                    response = await ChatService.process_message(head, content, db)
                    
                    # Send response
                    await websocket.send_json({
                        "type": "message",
                        "role": "head_of_council",
                        "content": response.get("content", "No response"),
                        "metadata": {
                            "agent_id": user_info['head_agentium_id'],
                            "model": response.get("model"),
                            "task_created": response.get("task_created"),
                            "task_id": response.get("task_id"),
                            "tokens_used": response.get("tokens_used")
                        },
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                except Exception as e:
                    print(f"[WebSocket] ChatService error: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "content": f"Error processing message: {str(e)}",
                        "timestamp": datetime.utcnow().isoformat()
                    })
            
            # Handle unknown message types
            else:
                await websocket.send_json({
                    "type": "error",
                    "content": f"Unknown message type: {message_type}",
                    "timestamp": datetime.utcnow().isoformat()
                })
    
    except WebSocketDisconnect:
        # Normal disconnection
        manager.disconnect(websocket)
        
    except Exception as e:
        # Unexpected error
        print(f"[WebSocket] Unexpected error: {e}")
        manager.disconnect(websocket)
        try:
            await websocket.close(code=1011, reason=f"Server error: {str(e)}")
        except:
            pass


@router.get("/ws/stats")
async def get_websocket_stats(current_user: dict = Depends(get_current_active_user)):
    """Get WebSocket connection statistics (admin only)."""
    return {
        "active_connections": manager.get_connection_count(),
        "connected_users": list(manager.user_connections.keys())
    }