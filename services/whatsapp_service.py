from typing import Any, Dict, List, Optional
from core.config import settings
from core.logging import get_logger
from services.meta_whatsapp_service import (
    send_meta_whatsapp_template,
    async_send_meta_whatsapp_template,
    async_send_meta_whatsapp_text,
    async_send_meta_template_by_type,
)

logger = get_logger(__name__)


class WhatsAppService:
    """WhatsApp service for sending messages via the Meta Cloud API."""

    async def send_message(
        self,
        to_phone: str,
        template_data: Dict[Any, Any],
        template_id: str,
        language: Optional[str] = None,
        button_payloads: Optional[List[str]] = None,
    ) -> dict:
        """
        Send a template message.

        Args:
            to_phone: Recipient phone number (format: +1234567890)
            template_data: Body variables keyed by position, e.g. {1: "Ana", 2: "Aspirin"}
            template_id: The Meta template name (stored in the templates table)
            language: Repo language name ('english', 'spanish', ...)
            button_payloads: Optional payloads for quick-reply buttons, in button order
        """
        return await async_send_meta_whatsapp_template(
            to_phone=to_phone,
            template_name=template_id,
            language=language,
            payload=template_data,
            button_payloads=button_payloads,
        )

    def send_message_sync(
        self,
        to_phone: str,
        template_data: Dict[Any, Any],
        template_id: str,
        language: Optional[str] = None,
        button_payloads: Optional[List[str]] = None,
    ) -> dict:
        """Blocking version of send_message, for Celery tasks and scripts."""
        return send_meta_whatsapp_template(
            to_phone=to_phone,
            template_name=template_id,
            language=language,
            payload=template_data,
            button_payloads=button_payloads,
        )

    async def send_template_by_type(
        self,
        db,
        template_type: str,
        to_phone: str,
        language: Optional[str],
        organization_id: Optional[int],
        template_data: Optional[Dict[Any, Any]] = None,
        button_payloads: Optional[List[str]] = None,
    ) -> dict:
        """Look up the active template of this type (AsyncSession) and send it."""
        return await async_send_meta_template_by_type(
            db,
            template_type=template_type,
            to_phone=to_phone,
            language=language,
            organization_id=organization_id,
            payload=template_data,
            button_payloads=button_payloads,
        )

    async def send_otp(
        self,
        db,
        to_phone: str,
        otp: str,
        language: Optional[str],
        organization_id: Optional[int] = None,
    ) -> dict:
        return await async_send_meta_template_by_type(
            db,
            template_type="otp",
            to_phone=to_phone,
            language=language,
            organization_id=organization_id,
            payload={1: otp},
            otp_button=otp if settings.META_WHATSAPP_OTP_HAS_COPY_BUTTON else None,
        )

    async def send_text(self, to_phone: str, text: str) -> dict:
        """Free-form text. Only valid within 24 hours of the user's last message."""
        return await async_send_meta_whatsapp_text(to_phone, text)


whatsapp_service = WhatsAppService()
