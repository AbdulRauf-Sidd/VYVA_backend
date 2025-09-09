import httpx
from typing import Dict, Any, Optional
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class WhatsAppService:
    """WhatsApp service for sending messages via Twilio."""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.from_number = settings.TWILIO_WHATSAPP_FROM_NUMBER
        self.template_sid = settings.TWILIO_WHATSAPP_TEMPLATE_SID
        
        if not self.account_sid:
            raise ValueError("TWILIO_ACCOUNT_SID is not configured")
        if not self.auth_token:
            raise ValueError("TWILIO_AUTH_TOKEN is not configured")
        if not self.from_number:
            raise ValueError("TWILIO_WHATSAPP_FROM_NUMBER is not configured")
        if not self.template_sid:
            raise ValueError("TWILIO_WHATSAPP_TEMPLATE_SID is not configured")
            
        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
    
    async def send_template_message(
        self,
        to_phone: str,
        template_sid: str,
        template_data: Dict[str, Any]
    ) -> bool:
        """
        Send a WhatsApp message using a Twilio template.
        
        Args:
            to_phone: Recipient phone number (format: +1234567890)
            template_sid: Twilio template SID
            template_data: Data to populate template variables
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Ensure phone number has whatsapp: prefix
            if not to_phone.startswith("whatsapp:"):
                to_phone = f"whatsapp:{to_phone}"
            
            # Prepare the message data
            message_data = {
                "From": self.from_number,
                "To": to_phone,
                "TemplateSid": template_sid,
                "TemplateData": template_data
            }
            
            # Send the message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    auth=(self.account_sid, self.auth_token),
                    data=message_data,
                    timeout=30.0
                )
                
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"WhatsApp message sent successfully to {to_phone}. Message SID: {result.get('sid', 'unknown')}")
                return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Twilio API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
    
    async def send_medical_report(
        self,
        recipient_phone: str,
        report_content: Dict[str, Any]
    ) -> bool:
        """
        Send a medical report via WhatsApp using the symptoms template.
        
        Args:
            recipient_phone: Recipient phone number
            report_content: Report content from the database
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Extract breakdown from report content
            breakdown = report_content.get('breakdown', {})
            
            # Convert breakdown to string format for template
            if isinstance(breakdown, dict):
                breakdown_text = "\n".join([f"{key}: {value}" for key, value in breakdown.items()])
            else:
                breakdown_text = str(breakdown)
            
            # Prepare template data
            template_data = {
                "breakdown": breakdown_text
            }
            
            # Send the template message
            success = await self.send_template_message(
                to_phone=recipient_phone,
                template_sid=self.template_sid,  # Use template SID from settings
                template_data=template_data
            )
            
            if success:
                logger.info(f"Medical report sent successfully via WhatsApp to {recipient_phone}")
                return True
            else:
                logger.error(f"Failed to send medical report via WhatsApp to {recipient_phone}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to send WhatsApp medical report to {recipient_phone}: {str(e)}")
            return False
    
    async def send_simple_message(
        self,
        to_phone: str,
        message: str
    ) -> bool:
        """
        Send a simple WhatsApp message (not using templates).
        
        Args:
            to_phone: Recipient phone number
            message: Message content
            
        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Ensure phone number has whatsapp: prefix
            if not to_phone.startswith("whatsapp:"):
                to_phone = f"whatsapp:{to_phone}"
            
            # Prepare the message data
            message_data = {
                "From": self.from_number,
                "To": to_phone,
                "Body": message
            }
            
            # Send the message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    auth=(self.account_sid, self.auth_token),
                    data=message_data,
                    timeout=30.0
                )
                
                response.raise_for_status()
                result = response.json()
                
                logger.info(f"WhatsApp message sent successfully to {to_phone}. Message SID: {result.get('sid', 'unknown')}")
                return True
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Twilio API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
