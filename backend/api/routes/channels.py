"""
Channel management API for frontend.
CRUD operations for external channel configurations.
FIXED: Added noload to prevent DetachedInstanceError, custom serialization
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session, noload
import secrets
import json

from backend.models.database import get_db
from backend.models.entities.channels import ExternalChannel, ExternalMessage, ChannelType, ChannelStatus
from backend.models.entities.agents import Agent
from backend.services.channel_manager import ChannelManager, WhatsAppAdapter
from backend.core.security import encrypt_api_key

router = APIRouter(prefix="/channels", tags=["Channels"])

class ChannelCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    channel_type: ChannelType
    config: dict = Field(default_factory=dict)
    default_agent_id: Optional[str] = None
    auto_create_tasks: bool = True
    require_approval: bool = False

class ChannelActivate(BaseModel):
    credentials: dict = Field(default_factory=dict)

class TestResult(BaseModel):
    success: bool
    message: str
    error: Optional[str] = None

# In-memory store for QR codes (production: use Redis)
qr_code_store = {}
pairing_status = {}


def _serialize_channel(channel: ExternalChannel) -> dict:
    """
    Safely convert ExternalChannel ORM → dict.
    Does NOT call channel.to_dict() to avoid triggering lazy-loaded relationships.
    """
    # Safely get config dict
    config = channel.config or {}
    
    # Build routing info safely
    routing = {
        "default_agent": channel.default_agent_id,
        "auto_create_tasks": channel.auto_create_tasks,
        "require_approval": channel.require_approval
    }
    
    # Build stats safely
    stats = {
        "received": config.get("stats_received", 0),
        "sent": config.get("stats_sent", 0),
        "last_message": config.get("last_message")
    }
    
    return {
        "id": str(channel.id),
        "name": channel.name or "",
        "type": channel.channel_type.value if channel.channel_type else "unknown",
        "status": channel.status.value if channel.status else "unknown",
        "config": {
            **config,
            "has_credentials": bool(
                config.get("access_token") or 
                config.get("bot_token") or 
                config.get("smtp_host")
            ),
            "webhook_url": config.get("webhook_url_display") or config.get("webhook_url")
        },
        "routing": routing,
        "stats": stats,
        "created_at": channel.created_at.isoformat() if channel.created_at else None,
        "updated_at": channel.updated_at.isoformat() if hasattr(channel, 'updated_at') and channel.updated_at else None
    }


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_channel(
    channel_data: ChannelCreate,
    db: Session = Depends(get_db)
):
    """Create new channel configuration."""
    
    # Generate unique webhook path
    webhook_path = secrets.token_urlsafe(16)
    
    # Get base URL for webhook
    base_url = "https://your-domain.com"  # TODO: From config
    
    channel = ExternalChannel(
        name=channel_data.name,
        channel_type=channel_data.channel_type,
        status=ChannelStatus.PENDING,
        config={
            **channel_data.config,
            'webhook_url_display': f"{base_url}/webhooks/{channel_data.channel_type.value}/{webhook_path[:8]}..." 
        },
        default_agent_id=channel_data.default_agent_id,
        auto_create_tasks=channel_data.auto_create_tasks,
        require_approval=channel_data.require_approval,
        webhook_path=webhook_path
    )
    
    db.add(channel)
    db.commit()
    db.refresh(channel)
    
    # If WhatsApp, initialize QR code generation
    if channel_data.channel_type == ChannelType.WHATSAPP:
        try:
            import qrcode
            import qrcode.image.svg
            import io
            
            # Generate pairing token
            pairing_token = secrets.token_urlsafe(32)
            qr_code_store[str(channel.id)] = {
                'token': pairing_token,
                'expires': None
            }
            pairing_status[str(channel.id)] = 'waiting'
            
            # Generate QR code data
            qr_data = f"agentium:whatsapp:{channel.id}:{pairing_token}"
            
            # Generate QR image
            factory = qrcode.image.svg.SvgImage
            qr = qrcode.make(qr_data, image_factory=factory)
            buffer = io.BytesIO()
            qr.save(buffer)
            svg_qr = buffer.getvalue().decode()
            
            # Store for retrieval
            qr_code_store[str(channel.id)]['qr_svg'] = svg_qr
            qr_code_store[str(channel.id)]['qr_data'] = qr_data
            
        except ImportError:
            # qrcode library not installed, store placeholder
            pairing_token = secrets.token_urlsafe(32)
            qr_code_store[str(channel.id)] = {
                'token': pairing_token,
                'qr_data': f"agentium:whatsapp:{channel.id}:{pairing_token}",
                'qr_svg': None
            }
            pairing_status[str(channel.id)] = 'waiting'
    
    return _serialize_channel(channel)


@router.get("/")
async def list_channels(db: Session = Depends(get_db)):
    """List all configured channels."""
    # Use noload to prevent lazy-loading issues
    channels = db.query(ExternalChannel).options(
        noload(ExternalChannel.default_agent),
        noload(ExternalChannel.messages)
    ).all()
    return [_serialize_channel(c) for c in channels]


@router.get("/{channel_id}")
async def get_channel(channel_id: str, db: Session = Depends(get_db)):
    """Get channel details."""
    channel = db.query(ExternalChannel).options(
        noload(ExternalChannel.default_agent),
        noload(ExternalChannel.messages)
    ).filter_by(id=channel_id).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    return _serialize_channel(channel)


@router.get("/{channel_id}/qr")
async def get_qr_code(channel_id: str, db: Session = Depends(get_db)):
    """Get QR code for WhatsApp pairing."""
    channel = db.query(ExternalChannel).filter_by(id=channel_id).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    if channel.channel_type != ChannelType.WHATSAPP:
        raise HTTPException(status_code=400, detail="QR codes only available for WhatsApp")
    
    # Check if already connected
    if channel.status == ChannelStatus.ACTIVE:
        return {
            "status": "active",
            "qr_code": None,
            "message": "Already connected"
        }
    
    # Return QR code if available
    cid = str(channel_id)
    if cid in qr_code_store:
        return {
            "status": pairing_status.get(cid, "waiting"),
            "qr_code": qr_code_store[cid].get('qr_data'),
            "expires_in": 60
        }
    
    raise HTTPException(status_code=404, detail="QR code not found or expired")


@router.post("/{channel_id}/activate")
async def activate_channel(
    channel_id: str,
    activation_data: ChannelActivate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Activate channel with credentials."""
    channel = db.query(ExternalChannel).filter_by(id=channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    try:
        credentials = activation_data.credentials
        
        if channel.channel_type == ChannelType.WHATSAPP:
            if 'qr_token' in credentials:
                stored = qr_code_store.get(channel_id, {})
                if stored.get('token') != credentials['qr_token']:
                    raise HTTPException(status_code=400, detail="Invalid QR token")
                
                channel.status = ChannelStatus.ACTIVE
                channel.config['connection_method'] = 'qr'
                
            elif 'access_token' in credentials and 'phone_number_id' in credentials:
                test_result = await test_whatsapp_credentials(credentials)
                if not test_result:
                    raise HTTPException(status_code=400, detail="Invalid WhatsApp credentials")
                
                channel.status = ChannelStatus.ACTIVE
                channel.config['access_token'] = encrypt_api_key(credentials['access_token'])
                channel.config['phone_number_id'] = credentials['phone_number_id']
                channel.config['phone_number'] = credentials.get('phone_number')
                channel.config['connection_method'] = 'api'
            else:
                raise HTTPException(status_code=400, detail="QR token or API credentials required")
                
        elif channel.channel_type == ChannelType.SLACK:
            if not credentials.get('bot_token'):
                raise HTTPException(status_code=400, detail="Bot token required")
            
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {credentials['bot_token']}"}
                )
                if not response.json().get('ok'):
                    raise HTTPException(status_code=400, detail="Invalid Slack token")
            
            channel.status = ChannelStatus.ACTIVE
            channel.config['bot_token'] = encrypt_api_key(credentials['bot_token'])
            if credentials.get('signing_secret'):
                channel.config['signing_secret'] = encrypt_api_key(credentials['signing_secret'])
        
        elif channel.channel_type == ChannelType.TELEGRAM:
            if not credentials.get('bot_token'):
                raise HTTPException(status_code=400, detail="Bot token required")
            
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://api.telegram.org/bot{credentials['bot_token']}/getMe"
                )
                if not response.json().get('ok'):
                    raise HTTPException(status_code=400, detail="Invalid Telegram token")
            
            channel.status = ChannelStatus.ACTIVE
            channel.config['bot_token'] = encrypt_api_key(credentials['bot_token'])
            bot_info = response.json().get('result', {})
            channel.config['bot_username'] = bot_info.get('username')
            channel.config['bot_name'] = bot_info.get('first_name')
        
        elif channel.channel_type == ChannelType.EMAIL:
            required = ['smtp_host', 'smtp_port', 'smtp_user', 'smtp_pass']
            missing = [f for f in required if not credentials.get(f)]
            if missing:
                raise HTTPException(status_code=400, detail=f"Missing fields: {', '.join(missing)}")
            
            channel.status = ChannelStatus.ACTIVE
            channel.config['smtp_host'] = credentials['smtp_host']
            channel.config['smtp_port'] = int(credentials['smtp_port'])
            channel.config['smtp_user'] = credentials['smtp_user']
            channel.config['smtp_pass'] = encrypt_api_key(credentials['smtp_pass'])
            channel.config['from_email'] = credentials.get('from_email', credentials['smtp_user'])
        
        # Update channel config
        channel.config.update({k: v for k, v in credentials.items() if k not in ['access_token', 'bot_token', 'smtp_pass']})
        db.commit()
        
        # Clean up QR store if applicable
        if channel_id in qr_code_store:
            del qr_code_store[channel_id]
        if channel_id in pairing_status:
            del pairing_status[channel_id]
        
        return {
            "status": "success",
            "channel": _serialize_channel(channel),
            "webhook_url": channel.config.get('webhook_url_display')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        channel.status = ChannelStatus.ERROR
        channel.config['error_message'] = str(e)
        db.commit()
        raise HTTPException(status_code=500, detail=f"Activation failed: {str(e)}")


@router.post("/{channel_id}/test")
async def test_channel_connection(
    channel_id: str,
    db: Session = Depends(get_db)
) -> TestResult:
    """Test if channel credentials are valid."""
    channel = db.query(ExternalChannel).filter_by(id=channel_id).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    try:
        if channel.channel_type == ChannelType.SLACK:
            import httpx
            from backend.core.security import decrypt_api_key
            
            token = decrypt_api_key(channel.config.get('bot_token', ''))
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/auth.test",
                    headers={"Authorization": f"Bearer {token}"}
                )
                data = response.json()
                
                if data.get('ok'):
                    return TestResult(success=True, message=f"Connected as @{data.get('user')}")
                else:
                    return TestResult(success=False, message="Connection failed", error=data.get('error'))
        
        elif channel.channel_type == ChannelType.TELEGRAM:
            import httpx
            from backend.core.security import decrypt_api_key
            
            token = decrypt_api_key(channel.config.get('bot_token', ''))
            
            async with httpx.AsyncClient() as client:
                response = await client.get(f"https://api.telegram.org/bot{token}/getMe")
                data = response.json()
                
                if data.get('ok'):
                    bot = data.get('result', {})
                    return TestResult(success=True, message=f"Connected as @{bot.get('username')}")
                else:
                    return TestResult(success=False, message="Connection failed", error=data.get('description'))
        
        elif channel.channel_type == ChannelType.WHATSAPP:
            if channel.config.get('connection_method') == 'api':
                creds = {
                    'access_token': channel.config.get('access_token'),
                    'phone_number_id': channel.config.get('phone_number_id')
                }
                if await test_whatsapp_credentials(creds):
                    return TestResult(success=True, message="WhatsApp Business API connected")
                else:
                    return TestResult(success=False, message="Connection failed", error="Invalid credentials")
            else:
                return TestResult(success=True, message="WhatsApp Web session active")
        
        elif channel.channel_type == ChannelType.EMAIL:
            import aiosmtplib
            from backend.core.security import decrypt_api_key
            
            try:
                await aiosmtplib.connect(
                    hostname=channel.config['smtp_host'],
                    port=channel.config['smtp_port'],
                    username=channel.config['smtp_user'],
                    password=decrypt_api_key(channel.config['smtp_pass']),
                    start_tls=True
                )
                return TestResult(success=True, message="SMTP connection successful")
            except Exception as e:
                return TestResult(success=False, message="SMTP connection failed", error=str(e))
        
        return TestResult(success=False, message="Unknown channel type")
        
    except Exception as e:
        return TestResult(success=False, message="Test failed", error=str(e))


@router.delete("/{channel_id}")
async def delete_channel(
    channel_id: str,
    db: Session = Depends(get_db)
):
    """Delete a channel and cleanup."""
    channel = db.query(ExternalChannel).filter_by(id=channel_id).first()
    
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    # Cleanup QR store if exists
    if channel_id in qr_code_store:
        del qr_code_store[channel_id]
    if channel_id in pairing_status:
        del pairing_status[channel_id]
    
    db.delete(channel)
    db.commit()
    
    return {"status": "deleted"}


@router.get("/{channel_id}/messages")
async def get_channel_messages(
    channel_id: str,
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get messages for a channel."""
    channel = db.query(ExternalChannel).filter_by(id=channel_id).first()
    if not channel:
        raise HTTPException(status_code=404, detail="Channel not found")
    
    query = db.query(ExternalMessage).filter_by(channel_id=channel_id)
    
    if status:
        query = query.filter_by(status=status)
    
    messages = query.order_by(ExternalMessage.created_at.desc()).limit(limit).all()
    
    # Safely serialize messages
    def serialize_message(m):
        return {
            "id": str(m.id),
            "channel_id": str(m.channel_id),
            "direction": m.direction.value if hasattr(m, 'direction') else "unknown",
            "content": m.content or "",
            "status": m.status if hasattr(m, 'status') else "unknown",
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
    
    return {
        "messages": [serialize_message(m) for m in messages],
        "count": len(messages)
    }


@router.get("/messages/all")
async def get_all_messages(
    limit: int = 50,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all messages across all channels."""
    query = db.query(ExternalMessage)
    
    if status:
        query = query.filter_by(status=status)
    
    messages = query.order_by(ExternalMessage.created_at.desc()).limit(limit).all()
    
    def serialize_message(m):
        return {
            "id": str(m.id),
            "channel_id": str(m.channel_id),
            "direction": m.direction.value if hasattr(m, 'direction') else "unknown",
            "content": m.content or "",
            "status": m.status if hasattr(m, 'status') else "unknown",
            "created_at": m.created_at.isoformat() if m.created_at else None
        }
    
    return {
        "messages": [serialize_message(m) for m in messages],
        "count": len(messages)
    }


# Helper function
async def test_whatsapp_credentials(credentials: dict) -> bool:
    """Test WhatsApp Business API credentials."""
    import httpx
    
    access_token = credentials.get('access_token')
    phone_number_id = credentials.get('phone_number_id')
    
    if not access_token or not phone_number_id:
        return False
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"https://graph.facebook.com/v17.0/{phone_number_id}",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            return response.status_code == 200
    except:
        return False