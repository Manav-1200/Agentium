
import asyncio
import sys
from unittest.mock import MagicMock, AsyncMock

# Mock dependencies
sys.modules["httpx"] = MagicMock()

from backend.services.channels.whatsapp import WhatsAppAdapter
from backend.services.channels.slack import SlackAdapter

# Mock data models to avoid SQLAlchemy issues
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass
class ExternalChannel:
    id: str
    config: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ExternalMessage:
    sender_id: str
    content: str

async def test_whatsapp_adapter():
    print("TEST: WhatsApp Adapter")
    
    # Mock channel
    channel = ExternalChannel(id="whatsapp-1", config={"phone_number_id": "123", "access_token": "abc"})
    adapter = WhatsAppAdapter(channel)
    
    # Mock message
    msg = ExternalMessage(sender_id="5551234", content="Hello")
    
    # Mock httpx response
    mock_response = MagicMock()
    mock_response.status_code = 200
    
    # Setup async context manager mock for httpx.AsyncClient
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post.return_value = mock_response
    
    import httpx
    httpx.AsyncClient.return_value = mock_client
    
    # Run
    result = await adapter.send_message(msg)
    
    # Assert
    print(f"Result: {result}")
    assert result
    mock_client.post.assert_called_once()
    print("TEST PASSED: WhatsApp send_message")

async def test_slack_adapter():
    print("\nTEST: Slack Adapter")
    
    # Mock channel
    channel = ExternalChannel(id="slack-1", config={"bot_token": "xoxb-123"})
    adapter = SlackAdapter(channel)
    
    # Mock message
    msg = ExternalMessage(sender_id="C12345", content="Hello Slack")
    
    # Mock httpx response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"ok": True}
    
    # Setup async context manager mock
    mock_client = AsyncMock()
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None
    mock_client.post.return_value = mock_response
    
    import httpx
    httpx.AsyncClient.return_value = mock_client
    
    # Run
    result = await adapter.send_message(msg)
    
    # Assert
    print(f"Result: {result}")
    assert result
    mock_client.post.assert_called_once()
    print("TEST PASSED: Slack send_message")

if __name__ == "__main__":
    asyncio.run(test_whatsapp_adapter())
    asyncio.run(test_slack_adapter())
