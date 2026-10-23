import httpx
from typing import Dict, Optional, Any
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# Repo language names -> Meta template language codes
META_LANGUAGE_MAP = {
    "english": "en",
    "spanish": "es",
    "german": "de",
    "french": "fr",
}


def send_meta_whatsapp_template(
    to_phone: str,
    template_name: str,
    language: str,
    payload: Optional[Dict[Any, Any]] = None,
) -> dict:
    """
    Send a WhatsApp template message via the Meta Cloud API.

    Args:
        to_phone: Recipient phone number (e.g. +1234567890)
        template_name: Approved Meta template name
        language: Repo language name ('english', 'spanish', ...) or an already-valid Meta code
        payload: Optional dynamic variables keyed by position, e.g. {1: "https://..."}
    """
    if not settings.META_WHATSAPP_ACCESS_TOKEN or not settings.META_WHATSAPP_PHONE_NUMBER_ID:
        raise ValueError("META_WHATSAPP_ACCESS_TOKEN / META_WHATSAPP_PHONE_NUMBER_ID are not configured")

    meta_language = META_LANGUAGE_MAP.get(language.lower(), language)

    template = {"name": template_name, "language": {"code": meta_language}}
    if payload:
        template["components"] = [{
            "type": "body",
            "parameters": [
                {"type": "text", "text": str(value)}
                for _, value in sorted(payload.items(), key=lambda kv: int(kv[0]))
            ],
        }]

    url = f"https://graph.facebook.com/{settings.META_WHATSAPP_API_VERSION}/{settings.META_WHATSAPP_PHONE_NUMBER_ID}/messages"
    body = {
        "messaging_product": "whatsapp",
        "to": to_phone.lstrip("+").replace("whatsapp:", "").lstrip("+"),
        "type": "template",
        "template": template,
    }

    response = httpx.post(
        url,
        headers={"Authorization": f"Bearer {settings.META_WHATSAPP_ACCESS_TOKEN}"},
        json=body,
        timeout=30.0,
    )
    if response.status_code >= 400:
        logger.error(f"Meta WhatsApp error {response.status_code}: {response.text}")
    response.raise_for_status()
    logger.info(f"Meta WhatsApp template '{template_name}' sent to {to_phone}: {response.json()}")
    return response.json()
