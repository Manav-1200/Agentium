"""
Chat API for Sovereign to communicate with Head of Council.
Supports streaming responses for real-time communication.
"""

from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities import Agent, HeadOfCouncil, Task
from backend.services.chat_service import ChatService
from backend.services.model_provider import ModelService

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatMessage(BaseModel):
    message: str
    stream: bool = True

class ChatResponse(BaseModel):
    response: str
    agent_id: str
    task_created: bool = False
    task_id: str = None

@router.post("/send", response_class=StreamingResponse)
async def send_message(
    chat_msg: ChatMessage,
    db: Session = Depends(get_db)
):
    """
    Send message to Head of Council (00001).
    Returns streaming response for real-time updates.
    """
    # Get Head of Council
    head = db.query(HeadOfCouncil).filter_by(agentium_id="00001").first()
    
    if not head:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Head of Council not initialized"
        )
    
    if head.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Head of Council is {head.status.value}"
        )
    
    # Check if we should stream
    if chat_msg.stream:
        return StreamingResponse(
            _stream_response(head, chat_msg.message, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # Non-streaming response
        response = await ChatService.process_message(head, chat_msg.message, db)
        return ChatResponse(
            response=response["content"],
            agent_id=head.agentium_id,
            task_created=response.get("task_created", False),
            task_id=response.get("task_id")
        )

async def _stream_response(
    head: HeadOfCouncil, 
    message: str, 
    db: Session
) -> AsyncGenerator[str, None]:
    """
    Stream response from Head of Council.
    Format: SSE (Server-Sent Events)
    """
    try:
        # Send initial "thinking" event
        yield f"data: {json.dumps({'type': 'status', 'content': 'Head of Council is deliberating...'})}\n\n"
        
        # Get model config
        config = head.get_model_config(db)
        if not config:
            yield f"data: {json.dumps({'type': 'error', 'content': 'No model configuration found'})}\n\n"
            return
        
        provider = await ModelService.get_provider("sovereign", config.id)
        if not provider:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to initialize AI provider'})}\n\n"
            return
        
        # Build system prompt from ethos
        system_prompt = head.get_system_prompt()
        
        # Add context about available agents
        context = await ChatService.get_system_context(db)
        full_prompt = f"""{system_prompt}

Current System State:
{context}

You are speaking directly to the Sovereign. Address them respectfully and provide clear, actionable responses."""

        # Stream the response
        full_response = []
        
        async for chunk in provider.stream_generate(full_prompt, message):
            full_response.append(chunk)
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        
        # Check if this should create a task
        full_text = "".join(full_response)
        task_info = await ChatService.analyze_for_task(head, message, full_text, db)
        
        # Send completion event with metadata
        yield f"""data: {json.dumps({
            'type': 'complete',
            'content': '',
            'metadata': {
                'agent_id': head.agentium_id,
                'model': config.default_model,
                'task_created': task_info['created'],
                'task_id': task_info.get('task_id')
            }
        })}\n\n"""
        
        # Log the interaction
        await ChatService.log_interaction(
            head.agentium_id,
            message,
            full_text,
            config.id,
            db
        )
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    finally:
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get chat history with Head of Council."""
    from backend.models.entities.audit import AuditLog
    
    logs = db.query(AuditLog).filter(
        AuditLog.actor_id == "00001",
        AuditLog.action == "chat_response"
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    return {
        "messages": [
            {
                "id": log.id,
                "role": "head_of_council",
                "content": log.after_state.get("response") if log.after_state else "",
                "timestamp": log.created_at.isoformat(),
                "metadata": {
                    "prompt": log.before_state.get("prompt") if log.before_state else ""
                }
            }
            for log in reversed(logs)
        ]
    }

import json
"""
Chat API for Sovereign to communicate with Head of Council.
Supports streaming responses for real-time communication.
"""

from typing import AsyncGenerator
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.entities import Agent, HeadOfCouncil, Task
from backend.services.chat_service import ChatService
from backend.services.model_provider import ModelService

router = APIRouter(prefix="/chat", tags=["Chat"])

class ChatMessage(BaseModel):
    message: str
    stream: bool = True

class ChatResponse(BaseModel):
    response: str
    agent_id: str
    task_created: bool = False
    task_id: str = None

@router.post("/send", response_class=StreamingResponse)
async def send_message(
    chat_msg: ChatMessage,
    db: Session = Depends(get_db)
):
    """
    Send message to Head of Council (00001).
    Returns streaming response for real-time updates.
    """
    # Get Head of Council
    head = db.query(HeadOfCouncil).filter_by(agentium_id="00001").first()
    
    if not head:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Head of Council not initialized"
        )
    
    if head.status.value != "active":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Head of Council is {head.status.value}"
        )
    
    # Check if we should stream
    if chat_msg.stream:
        return StreamingResponse(
            _stream_response(head, chat_msg.message, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"
            }
        )
    else:
        # Non-streaming response
        response = await ChatService.process_message(head, chat_msg.message, db)
        return ChatResponse(
            response=response["content"],
            agent_id=head.agentium_id,
            task_created=response.get("task_created", False),
            task_id=response.get("task_id")
        )

async def _stream_response(
    head: HeadOfCouncil, 
    message: str, 
    db: Session
) -> AsyncGenerator[str, None]:
    """
    Stream response from Head of Council.
    Format: SSE (Server-Sent Events)
    """
    try:
        # Send initial "thinking" event
        yield f"data: {json.dumps({'type': 'status', 'content': 'Head of Council is deliberating...'})}\n\n"
        
        # Get model config
        config = head.get_model_config(db)
        if not config:
            yield f"data: {json.dumps({'type': 'error', 'content': 'No model configuration found'})}\n\n"
            return
        
        provider = await ModelService.get_provider("sovereign", config.id)
        if not provider:
            yield f"data: {json.dumps({'type': 'error', 'content': 'Failed to initialize AI provider'})}\n\n"
            return
        
        # Build system prompt from ethos
        system_prompt = head.get_system_prompt()
        
        # Add context about available agents
        context = await ChatService.get_system_context(db)
        full_prompt = f"""{system_prompt}

Current System State:
{context}

You are speaking directly to the Sovereign. Address them respectfully and provide clear, actionable responses."""

        # Stream the response
        full_response = []
        
        async for chunk in provider.stream_generate(full_prompt, message):
            full_response.append(chunk)
            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
        
        # Check if this should create a task
        full_text = "".join(full_response)
        task_info = await ChatService.analyze_for_task(head, message, full_text, db)
        
        # Send completion event with metadata
        yield f"""data: {json.dumps({
            'type': 'complete',
            'content': '',
            'metadata': {
                'agent_id': head.agentium_id,
                'model': config.default_model,
                'task_created': task_info['created'],
                'task_id': task_info.get('task_id')
            }
        })}\n\n"""
        
        # Log the interaction
        await ChatService.log_interaction(
            head.agentium_id,
            message,
            full_text,
            config.id,
            db
        )
        
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    finally:
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

@router.get("/history")
async def get_chat_history(
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """Get chat history with Head of Council."""
    from backend.models.entities.audit import AuditLog
    
    logs = db.query(AuditLog).filter(
        AuditLog.actor_id == "00001",
        AuditLog.action == "chat_response"
    ).order_by(AuditLog.created_at.desc()).limit(limit).all()
    
    return {
        "messages": [
            {
                "id": log.id,
                "role": "head_of_council",
                "content": log.after_state.get("response") if log.after_state else "",
                "timestamp": log.created_at.isoformat(),
                "metadata": {
                    "prompt": log.before_state.get("prompt") if log.before_state else ""
                }
            }
            for log in reversed(logs)
        ]
    }

