from datetime import datetime, timezone

from sqlalchemy import select

from celery_app import celery_app
from core.database import SessionLocal
from core.logging import get_logger
from models.manual_whatsapp import ManualWhatsapp
from models.user import User
from services.meta_whatsapp_service import send_meta_whatsapp_template

logger = get_logger(__name__)


def fill_placeholders(value: str, user: User) -> str:
    """Per-user placeholders in variable values."""
    return (
        (value or "")
        .replace("{first_name}", user.first_name or "")
        .replace("{last_name}", user.last_name or "")
        .replace("{name}", user.full_name or user.first_name or "")
    )


def _send(db, item: ManualWhatsapp):
    user = db.get(User, item.user_id)
    if not user or not user.phone_number:
        raise ValueError("User or phone number not found")
    payload = {int(k): fill_placeholders(v, user) for k, v in (item.variables or {}).items()} or None
    result = send_meta_whatsapp_template(
        to_phone=user.phone_number,
        template_name=item.template_name,
        language=item.language,
        payload=payload,
    )
    item.wa_message_id = ((result.get("messages") or [{}])[0]).get("id")
    item.status = "sent"
    item.sent_at = datetime.now(timezone.utc)


@celery_app.task(name="dispatch_due_manual_whatsapp")
def dispatch_due_manual_whatsapp():
    """Runs every minute: claim due scheduled messages and send them."""
    db = SessionLocal()
    try:
        due = db.execute(
            select(ManualWhatsapp)
            .where(ManualWhatsapp.status == "scheduled", ManualWhatsapp.scheduled_at <= datetime.now(timezone.utc))
            .order_by(ManualWhatsapp.scheduled_at)
            .limit(100)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        for item in due:
            item.status = "queued"  # claimed, so another worker won't pick it up
        db.commit()

        for item in due:
            try:
                _send(db, item)
            except Exception as e:
                response = getattr(e, "response", None)
                logger.error(f"Manual WhatsApp {item.id} failed: {e}")
                item.status = "failed"
                item.error = (response.text if response is not None else str(e))[:1000]
            db.commit()
    except Exception as e:
        logger.error(f"dispatch_due_manual_whatsapp error: {e}")
        db.rollback()
    finally:
        db.close()
