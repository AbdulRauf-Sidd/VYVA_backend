import re
import httpx
from typing import Dict, List, Optional, Any
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

# Repo language names -> Meta template language codes
META_LANGUAGE_MAP = {
    "english": "en_US",
    "spanish": "es",
    "german": "de",
    "french": "fr",
}

# Meta limits for a template body parameter
MAX_PARAM_LENGTH = 1024


def meta_language(language: Optional[str]) -> str:
    language = language or "english"
    return META_LANGUAGE_MAP.get(language.lower(), language)


def _clean_param(value: Any) -> str:
    """Meta rejects template parameters with newlines, tabs or 5+ consecutive spaces."""
    text = "" if value is None else str(value)
    text = re.sub(r"\s*[\r\n\t]+\s*", ", ", text)
    text = re.sub(r" {5,}", "    ", text).strip()
    return text[:MAX_PARAM_LENGTH]


def quick_reply_payloads(ids: str, template_type: str) -> List[str]:
    """
    Payloads for the 'Yes' (button 0) and 'No' (button 1) quick replies, in the format the
    webhook parses: '<action>:<comma separated ids>:<template type>'.
    """
    return [f"Yes:{ids}:{template_type}", f"No:{ids}:{template_type}"]


def build_template_message(
    to_phone: str,
    template_name: str,
    language: Optional[str],
    payload: Optional[Dict[Any, Any]] = None,
    button_payloads: Optional[List[str]] = None,
    otp_button: Optional[str] = None,
) -> dict:
    """
    Build the Meta Cloud API body for a template message.

    payload: body variables keyed by position, e.g. {1: "Ana", 2: "Aspirin"}
    button_payloads: one payload per quick-reply button, in button order
    otp_button: the code for an authentication template's copy-code button
    """
    template = {"name": template_name, "language": {"code": meta_language(language)}}
    components = []

    if payload:
        components.append({
            "type": "body",
            "parameters": [
                {"type": "text", "text": _clean_param(value)}
                for _, value in sorted(payload.items(), key=lambda kv: int(kv[0]))
            ],
        })

    for index, button_payload in enumerate(button_payloads or []):
        components.append({
            "type": "button",
            "sub_type": "quick_reply",
            "index": str(index),
            "parameters": [{"type": "payload", "payload": button_payload}],
        })

    if otp_button:
        components.append({
            "type": "button",
            "sub_type": "url",
            "index": "0",
            "parameters": [{"type": "text", "text": otp_button}],
        })

    if components:
        template["components"] = components

    return {
        "messaging_product": "whatsapp",
        "to": normalize_phone(to_phone),
        "type": "template",
        "template": template,
    }


def normalize_phone(phone: str) -> str:
    """Meta wants digits only, no '+' and no 'whatsapp:' prefix."""
    return re.sub(r"\D", "", phone.replace("whatsapp:", ""))


def _request_parts():
    if not settings.META_WHATSAPP_ACCESS_TOKEN or not settings.META_WHATSAPP_PHONE_NUMBER_ID:
        raise ValueError("META_WHATSAPP_ACCESS_TOKEN / META_WHATSAPP_PHONE_NUMBER_ID are not configured")
    url = f"https://graph.facebook.com/{settings.META_WHATSAPP_API_VERSION}/{settings.META_WHATSAPP_PHONE_NUMBER_ID}/messages"
    headers = {"Authorization": f"Bearer {settings.META_WHATSAPP_ACCESS_TOKEN}"}
    return url, headers


def _handle_response(response: httpx.Response, description: str) -> dict:
    if response.status_code >= 400:
        logger.error(f"Meta WhatsApp error {response.status_code} sending {description}: {response.text}")
    response.raise_for_status()
    result = response.json()
    logger.info(f"Meta WhatsApp sent {description}: {result}")
    return result


def send_meta_whatsapp_template(
    to_phone: str,
    template_name: str,
    language: Optional[str],
    payload: Optional[Dict[Any, Any]] = None,
    button_payloads: Optional[List[str]] = None,
    otp_button: Optional[str] = None,
) -> dict:
    """
    Send a WhatsApp template message via the Meta Cloud API (blocking).

    Args:
        to_phone: Recipient phone number (e.g. +1234567890)
        template_name: Approved Meta template name
        language: Repo language name ('english', 'spanish', ...) or an already-valid Meta code
        payload: Optional body variables keyed by position, e.g. {1: "https://..."}
        button_payloads: Optional payloads for quick-reply buttons, in button order
    """
    body = build_template_message(to_phone, template_name, language, payload, button_payloads, otp_button)
    url, headers = _request_parts()
    response = httpx.post(url, headers=headers, json=body, timeout=30.0)
    return _handle_response(response, f"template '{template_name}' to {to_phone}")


async def async_send_meta_whatsapp_template(
    to_phone: str,
    template_name: str,
    language: Optional[str],
    payload: Optional[Dict[Any, Any]] = None,
    button_payloads: Optional[List[str]] = None,
    otp_button: Optional[str] = None,
) -> dict:
    """Async version of send_meta_whatsapp_template."""
    body = build_template_message(to_phone, template_name, language, payload, button_payloads, otp_button)
    url, headers = _request_parts()
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=body, timeout=30.0)
    return _handle_response(response, f"template '{template_name}' to {to_phone}")


async def async_send_meta_whatsapp_text(to_phone: str, text: str) -> dict:
    """
    Send a free-form text message. Meta only allows this within 24 hours of the
    user's last message, which is always the case when replying to a webhook event.
    """
    body = {
        "messaging_product": "whatsapp",
        "to": normalize_phone(to_phone),
        "type": "text",
        "text": {"body": text},
    }
    url, headers = _request_parts()
    async with httpx.AsyncClient() as client:
        response = await client.post(url, headers=headers, json=body, timeout=30.0)
    return _handle_response(response, f"text to {to_phone}")


def _template_query(template_type: str, language: Optional[str], organization_id: Optional[int]):
    from sqlalchemy import select, or_
    from models.organization import TwilioWhatsappTemplates as T

    return (
        select(T)
        .where(
            T.template_type == template_type,
            T.language == (language or "english"),
            T.is_active.is_(True),
            or_(T.organization_id == organization_id, T.organization_id.is_(None)),
        )
        # an organization-specific template wins over a global (NULL org) one
        .order_by(T.organization_id.is_(None))
    )


def find_template(db, template_type: str, language: Optional[str], organization_id: Optional[int]):
    """Active template of this type for the language (repo name, e.g. 'spanish'), or None. Sync session."""
    return db.execute(_template_query(template_type, language, organization_id)).scalars().first()


async def find_template_async(db, template_type: str, language: Optional[str], organization_id: Optional[int]):
    """Same as find_template for an AsyncSession."""
    result = await db.execute(_template_query(template_type, language, organization_id))
    return result.scalars().first()


def send_meta_template_by_type(
    db,
    template_type: str,
    to_phone: str,
    language: Optional[str],
    organization_id: Optional[int],
    payload: Optional[Dict[Any, Any]] = None,
    button_payloads: Optional[List[str]] = None,
) -> dict:
    """
    Look up the active template of `template_type` and send it via Meta (blocking, sync session).
    Raises ValueError if no template matches.
    """
    template = find_template(db, template_type, language, organization_id)
    if not template:
        raise ValueError(f"No active {template_type} template for language '{language or 'english'}'")
    return send_meta_whatsapp_template(
        to_phone=to_phone,
        template_name=template.template_id,
        language=language,
        payload=payload,
        button_payloads=button_payloads,
    )


async def async_send_meta_template_by_type(
    db,
    template_type: str,
    to_phone: str,
    language: Optional[str],
    organization_id: Optional[int],
    payload: Optional[Dict[Any, Any]] = None,
    button_payloads: Optional[List[str]] = None,
    otp_button: Optional[str] = None,
) -> dict:
    """Like send_meta_template_by_type, for an AsyncSession."""
    template = await find_template_async(db, template_type, language, organization_id)
    if not template:
        raise ValueError(f"No active {template_type} template for language '{language or 'english'}'")
    return await async_send_meta_whatsapp_template(
        to_phone=to_phone,
        template_name=template.template_id,
        language=language,
        payload=payload,
        button_payloads=button_payloads,
        otp_button=otp_button,
    )
