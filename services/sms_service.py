"""
SMS service for sending text messages.

Uses Twilio for SMS sending.
"""

from typing import Optional
from twilio.rest import Client
from twilio.base.exceptions import TwilioException
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class SMSService:
    """SMS service for sending text messages."""
    
    def __init__(self):
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        
        if all([self.account_sid, self.auth_token]):
            self.client = Client(self.account_sid, self.auth_token)
        else:
            self.client = None
            logger.warning("Twilio configuration incomplete")
    
    async def send_sms(
        self,
        to_number: str,
        message: str,
        from_number: Optional[str] = None
    ) -> bool:
        """Send an SMS message."""
        if not self.client:
            logger.warning("SMS service not configured, skipping SMS send")
            return False
        
        try:
            # Send SMS
            message_obj = self.client.messages.create(
                body=message,
                from_=from_number or self.phone_number,
                to=to_number
            )
            
            logger.info(f"SMS sent successfully to {to_number}, SID: {message_obj.sid}")
            return True
            
        except TwilioException as e:
            logger.error(f"Failed to send SMS to {to_number}: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to_number}: {str(e)}")
            return False
    
    async def send_emergency_alert(
        self,
        to_number: str,
        user_name: str,
        location: Optional[str] = None
    ) -> bool:
        """Send emergency alert SMS."""
        message = f"""
        EMERGENCY ALERT
        
        {user_name} may need immediate assistance.
        """
        
        if location:
            message += f"\nLocation: {location}"
        
        message += """
        
        Please respond immediately or contact emergency services if needed.
        """
        
        return await self.send_sms(to_number, message.strip())
    
    async def send_medication_reminder(
        self,
        to_number: str,
        user_name: str,
        medication_name: str,
        dosage: str
    ) -> bool:
        """Send medication reminder SMS."""
        message = f"""
        Medication Reminder
        
        Hello {user_name},
        
        It's time to take your medication:
        - {medication_name}
        - Dosage: {dosage}
        
        Please take your medication now.
        """
        
        return await self.send_sms(to_number, message.strip())
    
    async def send_appointment_reminder(
        self,
        to_number: str,
        user_name: str,
        appointment_type: str,
        date_time: str,
        location: Optional[str] = None
    ) -> bool:
        """Send appointment reminder SMS."""
        message = f"""
        Appointment Reminder
        
        Hello {user_name},
        
        You have an upcoming appointment:
        - Type: {appointment_type}
        - Date/Time: {date_time}
        """
        
        if location:
            message += f"- Location: {location}"
        
        message += "\n\nPlease arrive 10 minutes early."
        
        return await self.send_sms(to_number, message.strip()) 
    
    async def send_otp(
        self,
        to_number: str,
        otp_code: str
    ) -> bool:

        message = f"Your verification code is: {otp_code}"
        return await self.send_sms(to_number, message)
    
sms_service = SMSService()