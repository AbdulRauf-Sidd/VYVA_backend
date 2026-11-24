import re
from typing import Any, Optional

from sqlalchemy import select

from core.database import get_sync_session
from core.logging import get_logger
from models.user import User
from models.whatsapp_messages import WhatsappMessage

logger = get_logger(__name__)


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", (phone or "").replace("whatsapp:", ""))


def _user_id_for(db, digits: str) -> Optional[int]:
    return db.execute(select(User.id).where(User.phone_number == "+" + digits)).scalars().first()


def log_outgoing(
    to_phone: str,
    message_type: str,
    result: Optional[dict] = None,
    template_name: Optional[str] = None,
    body: Optional[str] = None,
    payload: Optional[dict] = None,
    error: Optional[str] = None,
) -> None:
    """Record a sent (or failed) message. Never raises: logging must not break sending."""
    try:
        wamid = None
        if result:
            wamid = ((result.get("messages") or [{}])[0]).get("id")
        digits = _digits(to_phone)
        with get_sync_session() as db:
            db.add(WhatsappMessage(
                direction="out",
                phone_number=digits,
                user_id=_user_id_for(db, digits),
                wa_message_id=wamid,
                message_type=message_type,
                template_name=template_name,
                body=body,
                payload=payload,
                status="failed" if error else "sent",
                error=error,
            ))
            db.commit()
    except Exception as e:
        logger.error(f"Failed to log outgoing WhatsApp message to {to_phone}: {e}")


def _incoming_body(message: dict) -> Optional[str]:
    mtype = message.get("type")
    if mtype == "text":
        return (message.get("text") or {}).get("body")
    if mtype == "button":
        return (message.get("button") or {}).get("text")
    if mtype == "interactive":
        interactive = message.get("interactive") or {}
        reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
        return reply.get("title")
    return None


def log_incoming(message: dict) -> None:
    """Record one message object from the webhook. Duplicate deliveries are ignored."""
    try:
        wamid = message.get("id")
        digits = _digits(message.get("from", ""))
        with get_sync_session() as db:
            if wamid and db.execute(select(WhatsappMessage.id).where(WhatsappMessage.wa_message_id == wamid)).first():
                return
            db.add(WhatsappMessage(
                direction="in",
                phone_number=digits,
                user_id=_user_id_for(db, digits),
                wa_message_id=wamid,
                message_type=message.get("type"),
                body=_incoming_body(message),
                payload=message,
                status="received",
            ))
            db.commit()
    except Exception as e:
        logger.error(f"Failed to log incoming WhatsApp message: {e}")


def update_status(status: dict) -> None:
    """Apply a delivery status (sent/delivered/read/failed) from the webhook to the outgoing row."""
    try:
        wamid = status.get("id")
        new_status = status.get("status")
        if not wamid or not new_status:
            return
        with get_sync_session() as db:
            row = db.execute(select(WhatsappMessage).where(WhatsappMessage.wa_message_id == wamid)).scalars().first()
            if not row:
                return
            # statuses can arrive out of order; never move backwards
            order = {"sent": 1, "delivered": 2, "read": 3}
            if new_status == "failed" or order.get(new_status, 0) >= order.get(row.status, 0):
                row.status = new_status
            if new_status == "failed":
                row.error = str(status.get("errors"))[:1000]
            db.commit()
    except Exception as e:
        logger.error(f"Failed to update WhatsApp message status: {e}")
