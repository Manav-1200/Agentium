#Test File Can be Deleted After Testing

import asyncio
import uuid
import sys
import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlalchemy.orm import Session
from backend.models.database import SessionLocal, init_db
from backend.models.entities.channels import ExternalChannel, ChannelStatus, ExternalMessage
from backend.models.entities.chat_message import ChatMessage, Conversation
from backend.models.entities.user import User
from backend.services.channel_manager import ChannelManager
from backend.services.channels.whatsapp_unified import UnifiedWhatsAppAdapter
from unittest.mock import AsyncMock

async def test_channel_flow(channel_type: str, raw_payload: dict, adapter_mock_class):
    print(f"\n--- Testing {channel_type.upper()} Flow ---")
    db = SessionLocal()
    try:
        # Ensure a user exists
        user = db.query(User).filter_by(is_admin=True, is_active=True).first()
        if not user:
            user = User(username="admin_test", email="admin_test@local", is_admin=True, is_active=True)
            db.add(user)
            db.commit()
            
        # Create a mock channel
        channel_id = str(uuid.uuid4())
        channel = ExternalChannel(
            id=channel_id,
            name=f"Test {channel_type}",
            channel_type=channel_type,
            user_id=str(user.id),
            status=ChannelStatus.ACTIVE,
            config={}
        )
        db.add(channel)
        db.commit()

        # Mock the adapter
        adapter_mock = adapter_mock_class()
        adapter_mock.send_message = AsyncMock(return_value=True)
        ChannelManager._adapters[channel_id] = adapter_mock
        ChannelManager._active_channels.add(channel_id)

        # 1. Simulate incoming message (Webhook -> receive_message)
        sender_id = f"user_{channel_type}"
        content = f"Hello from {channel_type}"
        
        print("1. Simulating incoming message...")
        ext_msg = await ChannelManager.receive_message(
            channel_id=channel_id,
            sender_id=sender_id,
            sender_name="Test User",
            content=content,
            message_type="text",
            raw_payload=raw_payload,
            db=db
        )
        
        assert ext_msg is not None, "Failed to create ExternalMessage"
        print(f"   Created ExternalMessage: {ext_msg.id}")

        # 2. Verify Unified Inbox Sync
        print("2. Verifying Unified Inbox Sync...")
        chat_msg = db.query(ChatMessage).filter_by(external_message_id=ext_msg.id).first()
        assert chat_msg is not None, "Failed to create unified ChatMessage"
        print(f"   Created ChatMessage: {chat_msg.id}")
        assert chat_msg.content == content, "Content mismatch"

        # 3. Simulate Outbound Reply (Unified Inbox -> send_response)
        print("3. Simulating outbound reply...")
        response_content = f"Reply to {channel_type}"
        sent = await ChannelManager.send_response(
            message_id=ext_msg.id,
            response_content=response_content,
            agent_id="admin",
            db=db
        )
        
        assert sent is True, "Failed to send response"
        adapter_mock.send_message.assert_called_once()
        print(f"   Successfully routed reply to adapter: {response_content}")
        
        # Verify status update
        db.refresh(chat_msg)
        assert chat_msg.status == "responded", f"Status not updated, got: {chat_msg.status}"
        print("   Status correctly updated to 'responded'")
        
        print(f"✅ {channel_type.upper()} flow verification complete!")
        
    finally:
        db.close()

async def main():
    init_db()
    
    # Mock adapter classes
    class MockAdapter:
        async def initialize(self): return True
        async def close(self): pass
        async def send_message(self, **kwargs): return True
        async def test_connection(self): return {"status": "success"}

    channels = [
        ("whatsapp-cloud", {"entry": [{"changes": [{"value": {"messages": [{"text": {"body": "hello"}}]}}]}]}),
        ("whatsapp-web-bridge", {"message": "hello"}),
        ("slack", {"event": {"text": "hello", "user": "U123"}}),
        ("telegram", {"message": {"text": "hello"}}),
        ("discord", {"content": "hello"}),
        ("email", {"text": "hello"})
    ]
    
    for c_type, payload in channels:
        try:
            await test_channel_flow(c_type, payload, MockAdapter)
        except Exception as e:
            print(f"❌ Failed {c_type}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
