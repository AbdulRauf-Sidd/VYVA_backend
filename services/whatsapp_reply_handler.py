import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from models.medication import MedicationLog
from models.organization import TemplateTypeEnum
from models.user import User
from scripts.medication_utils import build_medication_payload, update_med_logs
from scripts.utils import (
    generate_medication_whatsapp_response_message,
    generate_reminder_later_whatsapp_response_message,
)
from services.meta_whatsapp_service import quick_reply_payloads
from services.whatsapp_service import whatsapp_service
from tasks.utils import schedule_reminder_message

logger = logging.getLogger(__name__)


async def handle_button_payload(db: AsyncSession, phone_number: str, button_payload: str) -> Optional[str]:
    """
    Handle a quick-reply payload of the form '<action>:<comma separated ids>:<template type>'.
    Returns text to reply to the user with, or None if there is nothing to say.
    """
    user = (
        await db.execute(select(User).where(User.phone_number == phone_number))
    ).scalar_one_or_none()
    if not user:
        logger.warning(f"Button reply from unknown number {phone_number}: {button_payload}")
        return None

    parts = button_payload.split(":")
    if len(parts) < 2:
        logger.warning(f"Unexpected button payload format: {button_payload}")
        return None

    action = parts[0]
    template_type = parts[-1]
    reminder_ids = parts[1]
    med_log_ids = [int(x.strip()) for x in reminder_ids.split(",")]

    if template_type == TemplateTypeEnum.ask_for_reminder.value:
        if action == "Yes":
            logs = (
                await db.execute(
                    select(MedicationLog)
                    .where(MedicationLog.id.in_(med_log_ids))
                    .options(
                        selectinload(MedicationLog.medication),
                        selectinload(MedicationLog.medication_time),
                    )
                )
            ).scalars().all()
            meds = [build_medication_payload(log.medication, log.medication_time) for log in logs]

            payload = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone_number': user.phone_number,
                'language': user.preferred_consultation_language,
                'user_id': user.id,
                "medications": meds,
            }
            dt_utc = datetime.now(timezone.utc) + timedelta(minutes=15)
            schedule_reminder_message(payload, dt_utc=dt_utc, preferred_reminder_channel='whatsapp')

        return generate_reminder_later_whatsapp_response_message(user.preferred_consultation_language, action)

    if template_type == TemplateTypeEnum.medication_reminder.value:
        medication_taken = (action == "Yes")
        update_med_logs(user.id, medication_taken, med_log_ids)

        if not medication_taken:
            # Offer to be reminded again in 15 minutes
            await whatsapp_service.send_template_by_type(
                db,
                template_type=TemplateTypeEnum.ask_for_reminder.value,
                to_phone=user.phone_number,
                language=user.preferred_consultation_language,
                organization_id=user.organization_id,
                button_payloads=quick_reply_payloads(reminder_ids, TemplateTypeEnum.ask_for_reminder.value),
            )
            return None

        return generate_medication_whatsapp_response_message(user.preferred_consultation_language, medication_taken)

    logger.warning(f"Unhandled button payload: {button_payload}")
    return None
