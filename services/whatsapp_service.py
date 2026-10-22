import re
import httpx
from typing import Dict, Any, List, Optional
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# Language names stored in the DB -> WhatsApp template language codes.
LANGUAGE_CODES = {
    "english": "en",
    "spanish": "es",
    "german": "de",
    "french": "fr",
}


class WhatsAppService:
    """WhatsApp service for sending messages via the Meta WhatsApp Business Cloud API."""

    def __init__(self):
        self.access_token = settings.WHATSAPP_ACCESS_TOKEN
        self.phone_number_id = settings.WHATSAPP_PHONE_NUMBER_ID
        self.template_name = settings.WHATSAPP_TEMPLATE_NAME
        self.base_url = (
            f"https://graph.facebook.com/{settings.WHATSAPP_API_VERSION}/{self.phone_number_id}/messages"
        )

        if not self.access_token:
            logger.warning("WHATSAPP_ACCESS_TOKEN is not configured - WhatsApp service will be disabled")
            self.enabled = False
            return
        if not self.phone_number_id:
            logger.warning("WHATSAPP_PHONE_NUMBER_ID is not configured - WhatsApp service will be disabled")
            self.enabled = False
            return

        self.enabled = True

    # ------------------------------------------------------------------
    # Request building
    # ------------------------------------------------------------------

    @staticmethod
    def _format_to(to_phone: str) -> str:
        """Meta expects the number as digits only (E.164 without '+')."""
        return re.sub(r"\D", "", to_phone.replace("whatsapp:", ""))

    @staticmethod
    def _language_code(language: Optional[str]) -> str:
        if not language:
            return settings.WHATSAPP_DEFAULT_LANGUAGE
        return LANGUAGE_CODES.get(language.lower(), language)

    @staticmethod
    def _clean_param(value: Any) -> str:
        """Meta rejects empty parameters, newlines, tabs and runs of 4+ spaces in template parameters."""
        text = "" if value is None else str(value)
        text = re.sub(r"[\r\n\t]+", " ", text)
        text = re.sub(r" {4,}", "   ", text).strip()
        return text or "-"

    @staticmethod
    def _sort_key(key: Any):
        try:
            return (0, int(key))
        except (TypeError, ValueError):
            return (1, str(key))

    def _build_template_payload(
        self,
        to_phone: str,
        template_name: str,
        template_data: Optional[Dict[Any, Any]] = None,
        language: Optional[str] = None,
        quick_reply_payloads: Optional[List[str]] = None,
        button_text_params: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        template_data: positional body variables ({"1": ..., "2": ...} -> {{1}}, {{2}}).
        quick_reply_payloads: payload returned to the webhook for each quick-reply button, in button order.
        button_text_params: text parameter for URL/copy-code buttons, in button order.
        """
        components: List[Dict[str, Any]] = []

        if template_data:
            body_params = [
                {"type": "text", "text": self._clean_param(template_data[key])}
                for key in sorted(template_data.keys(), key=self._sort_key)
            ]
            components.append({"type": "body", "parameters": body_params})

        for index, payload in enumerate(quick_reply_payloads or []):
            components.append({
                "type": "button",
                "sub_type": "quick_reply",
                "index": str(index),
                "parameters": [{"type": "payload", "payload": payload}],
            })

        for index, text in enumerate(button_text_params or []):
            components.append({
                "type": "button",
                "sub_type": "url",
                "index": str(index),
                "parameters": [{"type": "text", "text": text}],
            })

        template: Dict[str, Any] = {
            "name": template_name,
            "language": {"code": self._language_code(language)},
        }
        if components:
            template["components"] = components

        return {
            "messaging_product": "whatsapp",
            "to": self._format_to(to_phone),
            "type": "template",
            "template": template,
        }

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _check_response(response: httpx.Response) -> httpx.Response:
        """Log Meta's error body (it explains template/parameter problems) before raising."""
        if response.is_error:
            logger.error(f"WhatsApp API error: {response.status_code} - {response.text}")
        response.raise_for_status()
        return response

    async def _post(self, payload: Dict[str, Any]) -> httpx.Response:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.base_url, json=payload, headers=self._headers(), timeout=30.0
            )
        return self._check_response(response)

    def _post_sync(self, payload: Dict[str, Any]) -> httpx.Response:
        with httpx.Client() as client:
            response = client.post(
                self.base_url, json=payload, headers=self._headers(), timeout=30.0
            )
        return self._check_response(response)

    @staticmethod
    def _message_id(response: httpx.Response) -> str:
        try:
            return response.json()["messages"][0]["id"]
        except Exception:
            return "unknown"

    # ------------------------------------------------------------------
    # Sending
    # ------------------------------------------------------------------

    async def send_template_message(
        self,
        to_phone: str,
        template_data: Dict[str, Any],
        language: Optional[str] = None,
    ) -> bool:
        """
        Send the default WhatsApp template (WHATSAPP_TEMPLATE_NAME).

        Args:
            to_phone: Recipient phone number (format: +1234567890)
            template_data: Data to populate template variables
        """
        if not self.enabled:
            logger.warning("WhatsApp service is disabled - cannot send template message")
            return False
        try:
            if not self.template_name:
                logger.error("WHATSAPP_TEMPLATE_NAME is not configured")
                return False

            logger.info(f"Sending template '{self.template_name}' with data: {template_data}")
            payload = self._build_template_payload(to_phone, self.template_name, template_data, language)
            response = await self._post(payload)

            logger.info(
                f"WhatsApp message sent successfully to {to_phone}. Message ID: {self._message_id(response)}")
            return True

        except httpx.HTTPStatusError:
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False

    async def send_medical_report(
        self,
        recipient_phone: str,
        report_content: Dict[str, Any]
    ) -> bool:
        try:

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
        """Send a free-form text message. WhatsApp only delivers these within 24h of the user's last message."""
        if not self.enabled:
            logger.warning("WhatsApp service is disabled - cannot send text message")
            return False
        try:
            payload = {
                "messaging_product": "whatsapp",
                "to": self._format_to(to_phone),
                "type": "text",
                "text": {"body": message},
            }
            response = await self._post(payload)

            logger.info(
                f"WhatsApp message sent successfully to {to_phone}. Message ID: {self._message_id(response)}")
            return True

        except httpx.HTTPStatusError:
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False

    async def send_reminder_message(
        self,
        to_phone: str,
        template_data: Dict[str, Any],
        template_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bool:
        template_id = template_id or settings.WHATSAPP_REMINDER_TEMPLATE_NAME
        try:
            if not template_id:
                logger.error("Template name is required")
                return False

            logger.info(f"Sending template '{template_id}' with data: {template_data}")
            payload = self._build_template_payload(to_phone, template_id, template_data, language)
            response = await self._post(payload)

            logger.info(
                f"WhatsApp message sent successfully to {to_phone}. Message ID: {self._message_id(response)}")
            return True

        except httpx.HTTPStatusError:
            return False
        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return False

    async def send_onboarding_message(
        self,
        to_phone: str,
        template_data: Dict[str, Any],
        template_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bool:
        template_id = template_id or settings.WHATSAPP_ONBOARDING_TEMPLATE_NAME
        payload = self._build_template_payload(to_phone, template_id, template_data, language)
        await self._post(payload)
        return True

    async def send_otp(
        self,
        to_phone: str,
        otp: str,
        template_id: Optional[str] = None,
        language: Optional[str] = None,
    ) -> bool:
        template_id = template_id or settings.WHATSAPP_OTP_TEMPLATE_NAME
        payload = self._build_template_payload(
            to_phone,
            template_id,
            {1: otp},
            language,
            button_text_params=[str(otp)] if settings.WHATSAPP_OTP_USES_BUTTON else None,
        )
        await self._post(payload)
        return True

    async def send_message(
        self,
        to_phone: str,
        template_data: dict,
        template_id: str,
        language: Optional[str] = None,
        quick_reply_payloads: Optional[List[str]] = None,
    ) -> httpx.Response:
        payload = self._build_template_payload(
            to_phone, template_id, template_data, language, quick_reply_payloads
        )
        response = await self._post(payload)
        logger.info(f"WhatsApp message sent to {to_phone}. Message ID: {self._message_id(response)}")
        return response

    def send_message_sync(
        self,
        to_phone: str,
        template_data: dict,
        template_id: str,
        language: Optional[str] = None,
        quick_reply_payloads: Optional[List[str]] = None,
    ) -> httpx.Response:
        payload = self._build_template_payload(
            to_phone, template_id, template_data, language, quick_reply_payloads
        )
        response = self._post_sync(payload)
        logger.info(f"WhatsApp message sent to {to_phone}. Message ID: {self._message_id(response)}")
        return response


whatsapp_service = WhatsAppService()
