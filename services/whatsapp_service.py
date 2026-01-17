import httpx
import json
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
            logger.warning("TWILIO_ACCOUNT_SID is not configured - WhatsApp service will be disabled")
            self.enabled = False
            return
        if not self.auth_token:
            logger.warning("TWILIO_AUTH_TOKEN is not configured - WhatsApp service will be disabled")
            self.enabled = False
            return
        if not self.from_number:
            logger.warning("TWILIO_WHATSAPP_FROM_NUMBER is not configured - WhatsApp service will be disabled")
            self.enabled = False
            return
        
        self.enabled = True
        # Template SID is optional - only required for template messages

        self.base_url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"

    def _sanitize_template_variable(self, value: str) -> str:
        """
        Sanitize template variable values to avoid Twilio error 21656.
        
        Args:
            value: The variable value to sanitize
            
        Returns:
            str: Sanitized value
        """
        if not isinstance(value, str):
            value = str(value)
        
        # Replace problematic characters that can cause error 21656
        # Replace straight apostrophe with right single quotation mark
        value = value.replace("'", "'")
        
        # Remove or replace other problematic characters if needed
        # Add more replacements as needed based on your specific use case
        
        return value

    async def send_template_message(
        self,
        to_phone: str,
        template_data: Dict[str, Any]
    ) -> bool:
        """
        Send a WhatsApp message using a Twilio template.

        Args:
            to_phone: Recipient phone number (format: +1234567890)
            template_data: Data to populate template variables
        """
        if not self.enabled:
            logger.warning("WhatsApp service is disabled - cannot send template message")
            return False
        try:
            # Check if template_sid is configured
            if not self.template_sid:
                logger.error("TWILIO_WHATSAPP_TEMPLATE_SID is not configured")
                return False
            # Ensure phone number has whatsapp: prefix
            if not to_phone.startswith("whatsapp:"):
                to_phone = f"whatsapp:{to_phone}"

            from_number = self.from_number
            if not from_number.startswith("whatsapp:"):
                from_number = f"whatsapp:{from_number}"

            # Prepare the message data for form URL encoding
            # ContentVariables must be a JSON string, not a list
            content_variables_json = json.dumps(template_data)
            logger.info(f"Template data: {template_data}")
            # Log the data being sent for debugging
            logger.info(f"Sending template message with ContentSid: {self.template_sid}")
            logger.info(f"ContentVariables: {content_variables_json}")
            
            message_data = {
                "From": from_number,
                "To": to_phone,
                "ContentSid": self.template_sid,
                "ContentVariables": content_variables_json
            }

            # Send the message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    auth=(self.account_sid, self.auth_token),
                    data=message_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"WhatsApp message sent successfully to {to_phone}. Message SID: {result.get('sid', 'unknown')}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Twilio API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
        
    async def send_sms(
        self,
        to_phone: str,
        body: str
    ) -> bool:
        """
        Send a WhatsApp message using a Twilio template.

        Args:
            to_phone: Recipient phone number (format: +1234567890)
            template_data: Data to populate template variables

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Check if template_sid is configured
            
            # Ensure phone number has whatsapp: prefix
            
            logger.info(f"SMS Body: {body}")
            # Log the data being sent for debugging

            
            message_data = {
                "From": "+18782842340",
                "To": to_phone,
                "Body": body
            }

            # Send the message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    auth=(self.account_sid, self.auth_token),
                    data=message_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"WhatsApp message sent successfully to {to_phone}. Message SID: {result.get('sid', 'unknown')}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Twilio API error: {e.response.status_code} - {e.response.text}")
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
            # breakdown = report_content.get('breakdown', {})

            # Use breakdown directly as template data if it's a dict
            # This allows for multiple template variables like {{1}}, {{2}}, etc.
            # if isinstance(breakdown, dict):
            #     template_data = breakdown
            # else:
            #     # If breakdown is not a dict, convert to string and use as single variable
            #     breakdown_text = str(breakdown)
            #     template_data = {
            #         "breakdown": breakdown_text
            #     }

            logger.info(f"Sending Report content: {report_content}")
            # Send the template message
            success = await self.send_template_message(
                to_phone=recipient_phone,
                template_data=report_content
            )

            if success:
                logger.info(
                    f"Medical report sent successfully via WhatsApp to {recipient_phone}")
                return True
            else:
                logger.error(
                    f"Failed to send medical report via WhatsApp to {recipient_phone}")
                return False

        except Exception as e:
            logger.error(
                f"Failed to send WhatsApp medical report to {recipient_phone}: {str(e)}")
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

                logger.info(
                    f"WhatsApp message sent successfully to {to_phone}. Message SID: {result.get('sid', 'unknown')}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Twilio API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False

    async def send_reminder_message(
        self,
        to_phone: str,
        template_data: Dict[str, Any],
        template_id: str = settings.TWILIO_WHATSAPP_REMINDER_TEMPLATE_SID
    ) -> bool:
        """
        Send a WhatsApp message using a Twilio template.

        Args:
            to_phone: Recipient phone number (format: +1234567890)
            template_data: Data to populate template variables

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Check if template_sid is configured
            if not template_id:
                logger.error("Template id is required")
                return False
            # Ensure phone number has whatsapp: prefix
            if not to_phone.startswith("whatsapp:"):
                to_phone = f"whatsapp:{to_phone}"

            from_number = self.from_number
            if not from_number.startswith("whatsapp:"):
                from_number = f"whatsapp:{from_number}"

            # Prepare the message data for form URL encoding
            # ContentVariables must be a JSON string, not a list
            content_variables_json = json.dumps(template_data)
            
            # Log the data being sent for debugging
            logger.info(f"Sending template message with ContentSid: {template_id}")
            logger.info(f"ContentVariables: {content_variables_json}")
            
            message_data = {
                "From": from_number,
                "To": to_phone,
                "ContentSid": template_id,
                "ContentVariables": content_variables_json
            }

            # Send the message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    auth=(self.account_sid, self.auth_token),
                    data=message_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"WhatsApp message sent successfully to {to_phone}. Message SID: {result.get('sid', 'unknown')}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Twilio API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
        
    
    async def send_brain_coach_report(
        self,
        to_phone: str,
        template_data: Dict[str, Any],
        template_id: str = settings.TWILIO_WHATSAPP_BRAIN_COACH_TEMPLATE_SID
    ) -> bool:
        """
        Send a WhatsApp message using a Twilio template.

        Args:
            to_phone: Recipient phone number (format: +1234567890)
            template_data: Data to populate template variables

        Returns:
            bool: True if message sent successfully, False otherwise
        """
        try:
            # Check if template_sid is configured
            if not template_id:
                logger.error("Template id is required")
                return False
            # Ensure phone number has whatsapp: prefix
            if not to_phone.startswith("whatsapp:"):
                to_phone = f"whatsapp:{to_phone}"

            from_number = self.from_number
            if not from_number.startswith("whatsapp:"):
                from_number = f"whatsapp:{from_number}"

            # Prepare the message data for form URL encoding
            # ContentVariables must be a JSON string, not a list
            content_variables_json = json.dumps(template_data)
            
            # Log the data being sent for debugging
            logger.info(f"Sending template message with ContentSid: {template_id}")
            logger.info(f"ContentVariables: {content_variables_json}")
            
            message_data = {
                "From": from_number,
                "To": to_phone,
                "ContentSid": template_id,
                "ContentVariables": content_variables_json
            }

            # Send the message
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    auth=(self.account_sid, self.auth_token),
                    data=message_data,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    timeout=30.0
                )

                response.raise_for_status()
                result = response.json()

                logger.info(
                    f"WhatsApp message sent successfully to {to_phone}. Message SID: {result.get('sid', 'unknown')}")
                return True

        except httpx.HTTPStatusError as e:
            logger.error(
                f"Twilio API error: {e.response.status_code} - {e.response.text}")
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False
        

    async def send_onboarding_message(
        self,
        to_phone: str,
        template_data: Dict[str, Any],
        template_id: str = settings.TWILIO_WHATSAPP_ONBOARDING_TEMPLATE_SID
    ) -> bool:
        content_variables_json = json.dumps(template_data)

        # Ensure phone number has whatsapp: prefix
        if not to_phone.startswith("whatsapp:"):
            to_phone = f"whatsapp:{to_phone}"
            
        from_number = self.from_number
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        message_data = {
                "From": from_number,
                "To": to_phone,
                "ContentSid": template_id,
                "ContentVariables": content_variables_json
            }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                auth=(self.account_sid, self.auth_token),
                data=message_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )
            response.raise_for_status()
            return True
        
    async def send_otp(
        self,
        to_phone: str,
        otp: str,
        template_id: str = settings.TWILIO_WHATSAPP_OTP_TEMPLATE_SID
    ) -> bool:
        template_data = {
            1: otp
        }
        content_variables_json = json.dumps(template_data)

        # Ensure phone number has whatsapp: prefix
        if not to_phone.startswith("whatsapp:"):
            to_phone = f"whatsapp:{to_phone}"
            
        from_number = self.from_number
        if not from_number.startswith("whatsapp:"):
            from_number = f"whatsapp:{from_number}"

        message_data = {
                "From": from_number,
                "To": to_phone,
                "ContentSid": template_id,
                "ContentVariables": content_variables_json
            }
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url,
                auth=(self.account_sid, self.auth_token),
                data=message_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0
            )
            response.raise_for_status()
            return True
        
whatsapp_service = WhatsAppService()