
import httpx
import logging
from typing import Dict, Any, Optional

from backend.services.channels.base import BaseChannelAdapter
from backend.models.entities.channels import ExternalMessage

logger = logging.getLogger(__name__)

class WhatsAppAdapter(BaseChannelAdapter):
    """
    Adapter for WhatsApp Cloud API.
    """
    
    BASE_URL = "https://graph.facebook.com/v17.0"

    async def send_message(self, message: ExternalMessage) -> bool:
        """
        Send a WhatsApp message via Cloud API.
        """
        phone_number_id = self.config.get("phone_number_id")
        access_token = self.config.get("access_token")
        to_number = message.sender_id  # Assuming sender_id is the phone number
        
        if not all([phone_number_id, access_token, to_number]):
            logger.error(f"[WhatsApp] Missing configuration for channel {self.channel.id}")
            return False
            
        url = f"{self.BASE_URL}/{phone_number_id}/messages"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "text",
            "text": {"body": message.content}
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, headers=headers, json=payload, timeout=10.0)
                
            if response.status_code in (200, 201):
                return True
            else:
                logger.error(f"[WhatsApp] Failed to send: {response.text}")
                return False
        except Exception as e:
            logger.error(f"[WhatsApp] Exception sending message: {e}")
            return False

    async def validate_config(self) -> bool:
        return all(k in self.config for k in ["phone_number_id", "access_token"])
