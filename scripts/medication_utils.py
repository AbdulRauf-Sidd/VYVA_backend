import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import Caretaker, User
from models.organization import TwilioWhatsappTemplates, TemplateTypeEnum
from models.medication import MedicationStatus, MedicationLog
from core.database import SessionLocal
from sqlalchemy.orm import selectinload
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)


def update_med_logs(user_id: int, medication_taken: bool, med_log_ids: list[int]):
    if not med_log_ids:
        return

    db = SessionLocal()
    try:
        status = (
            MedicationStatus.TAKEN.value
            if medication_taken
            else MedicationStatus.MISSED.value
        )

        values = {
            "status": status,
            "taken_at": datetime.now(timezone.utc) if medication_taken else None,
        }

        db.execute(
            update(MedicationLog)
            .where(
                MedicationLog.id.in_(med_log_ids),
                MedicationLog.user_id == user_id,
            )
            .values(**values)
        )

        db.commit()
    except Exception as e:
        logger.error(f"error in update_med_log: {e}")
    finally:
        db.close()
    


def notify_caretaker_on_missed_meds(user_id: int):
    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .options(selectinload(User.caretaker))
            .filter(User.id == user_id)
            .first()
        )

        if not user:
            logger.warning(f"User not found: {user_id}")
            return False

        caretaker = user.caretaker
        if not caretaker:
            logger.info(f"No caretaker assigned for user {user_id}")
            return False

        caretaker_phone = caretaker.phone_number
        caretaker_name = caretaker.name
        channel = caretaker.preferred_notification_channel
        if channel == "whatsapp":
            template = (
                db.query(TwilioWhatsappTemplates)
                .filter(
                    TwilioWhatsappTemplates.template_type == TemplateTypeEnum.MEDICATION_REMINDER,
                    TwilioWhatsappTemplates.language == caretaker.language,
                )
                .first()
            )
            if not template:
                logger.error("Notify Caretaker error: twilio whatsapp template now found")
                return
            
            message_template ={
                1: caretaker_name,
                2: user.full_name
            }

            success = whatsapp_service.send_message(caretaker_phone, message_template, template.id)
            if not success:
                logger.error("Notify Caretaker error: message not sent")
                return
        elif channel == 'phone':
            pass
            #TODO
        else:
            logger.error(f"Notify Caretaker error: unkown channel {channel} for notification")

        return True

    except Exception:
        logger.exception("Failed to notify caretaker on missed meds")
        return False
    finally:
        db.close()


def construct_medication_string_for_whatsapp(medications):
    return ", ".join(
        f"{med['medication_name']} {med['medication_dosage']}"
        for med in medications
    )