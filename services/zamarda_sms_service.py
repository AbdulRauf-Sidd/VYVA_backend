"""
SMS service for sending text messages.

Uses Zamarda (Zadarma API, POST /v1/sms/send/) for SMS sending.
"""

import base64
import hashlib
import hmac
from typing import Optional
from urllib.parse import quote_plus, urlencode

import httpx

from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

API_HOST = "https://api.zadarma.com"
SMS_METHOD = "/v1/sms/send/"


class ZamardaSMSService:
    """SMS service for sending text messages through Zamarda."""

    def __init__(self):
        self.api_key = settings.ZAMARDA_API_KEY
        self.api_secret = settings.ZAMARDA_API_SECRET
        self.configured = all([self.api_key, self.api_secret])

        if not self.configured:
            logger.warning("Zamarda configuration incomplete")

    def _build_request(self, to_number: str, message: str, sender: Optional[str]):
        # Zamarda expects digits only, no '+'.
        params = {"number": to_number.lstrip("+"), "message": message}
        if sender:
            params["sender"] = sender

        # Signature: base64(hex(hmac_sha1(method + params + md5(params), secret)))
        params_str = urlencode(sorted(params.items()), quote_via=quote_plus)
        data = SMS_METHOD + params_str + hashlib.md5(params_str.encode()).hexdigest()
        hex_digest = hmac.new(self.api_secret.encode(), data.encode(), hashlib.sha1).hexdigest()
        signature = base64.b64encode(hex_digest.encode()).decode()

        headers = {"Authorization": f"{self.api_key}:{signature}"}
        return params, headers

    @staticmethod
    def _is_success(response: httpx.Response) -> bool:
        try:
            return response.is_success and response.json().get("status") == "success"
        except ValueError:
            return False

    async def send_sms(
        self,
        to_number: str,
        message: str,
        sender: Optional[str] = None
    ) -> bool:
        """Send an SMS message."""
        if not self.configured:
            logger.warning("Zamarda SMS service not configured, skipping SMS send")
            return False

        try:
            params, headers = self._build_request(to_number, message, sender)
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    API_HOST + SMS_METHOD, data=params, headers=headers, timeout=30.0
                )

            if self._is_success(response):
                logger.info(f"SMS sent successfully to {to_number}")
                return True

            logger.error(f"Failed to send SMS to {to_number}: {response.status_code} - {response.text}")
            return False

        except Exception as e:
            logger.error(f"Unexpected error sending SMS to {to_number}: {str(e)}")
            return False

    def send_sms_sync(
        self,
        to_number: str,
        message: str,
        sender: Optional[str] = None
    ) -> bool:
        """Send an SMS message (blocking)."""
        if not self.configured:
            logger.warning("Zamarda SMS service not configured, skipping SMS send")
            return False

        try:
            params, headers = self._build_request(to_number, message, sender)
            response = httpx.post(
                API_HOST + SMS_METHOD, data=params, headers=headers, timeout=30.0
            )

            if self._is_success(response):
                logger.info(f"SMS sent successfully to {to_number}")
                return True

            logger.error(f"Failed to send SMS to {to_number}: {response.status_code} - {response.text}")
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

    async def send_magic_link(
        self,
        to_number: str,
        token: str,
        domain: str
    ) -> bool:
        """Send magic login link via SMS."""
        magic_link = f"https://{domain}.vyva.io/magic-login?token={token}"
        message = f"Welcome to VYVA! Tap the link to get started: {magic_link}"
        return await self.send_sms(to_number, message)

    async def send_otp(
        self,
        to_number: str,
        otp_code: str
    ) -> bool:
        """Send OTP verification code via SMS."""
        message = f"Your verification code is: {otp_code}"
        return await self.send_sms(to_number, message)


zamarda_sms_service = ZamardaSMSService()
