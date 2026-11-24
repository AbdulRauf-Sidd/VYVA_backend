import hashlib
import hmac
import json
import asyncio
import logging

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database import get_db
from services.whatsapp_message_log import log_incoming, update_status
from services.whatsapp_reply_handler import handle_button_payload
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta calls this once when the webhook is saved in the dashboard."""
    if (
        hub_mode == "subscribe"
        and settings.META_WEBHOOK_VERIFY_TOKEN
        and hmac.compare_digest(hub_verify_token or "", settings.META_WEBHOOK_VERIFY_TOKEN)
    ):
        return PlainTextResponse(hub_challenge)
    return Response(status_code=403)


def _signature_valid(body: bytes, header: str) -> bool:
    if not settings.META_APP_SECRET:
        logger.error("META_APP_SECRET is not configured, rejecting WhatsApp webhook")
        return False
    expected = "sha256=" + hmac.new(settings.META_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header or "")


def _button_payload(message: dict):
    """The payload of a quick-reply tap, or None for any other kind of message."""
    if message.get("type") == "button":
        return (message.get("button") or {}).get("payload")
    if message.get("type") == "interactive":
        return ((message.get("interactive") or {}).get("button_reply") or {}).get("id")
    return None


@router.post("/webhook")
async def receive_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Incoming WhatsApp events from Meta: replies to our templates, and delivery statuses."""
    body = await request.body()
    if not _signature_valid(body, request.headers.get("X-Hub-Signature-256")):
        return Response(status_code=403)

    # Always answer 200 once the signature is valid, otherwise Meta keeps retrying the event.
    try:
        data = json.loads(body)
        for entry in data.get("entry", []):
            for change in entry.get("changes", []):
                value = change.get("value") or {}

                for status in value.get("statuses", []):
                    await asyncio.to_thread(update_status, status)
                    if status.get("status") == "failed":
                        logger.error(f"WhatsApp message to {status.get('recipient_id')} failed: {status.get('errors')}")

                for message in value.get("messages", []):
                    await asyncio.to_thread(log_incoming, message)
                    button_payload = _button_payload(message)
                    if not button_payload:
                        continue

                    phone_number = "+" + message["from"]
                    try:
                        reply = await handle_button_payload(db, phone_number, button_payload)
                        if reply:
                            await whatsapp_service.send_text(phone_number, reply)
                    except Exception as e:
                        logger.error(f"Error handling button reply '{button_payload}' from {phone_number}: {e}")
    except Exception as e:
        logger.exception(f"Error processing WhatsApp webhook: {e}")

    return Response(status_code=200)
