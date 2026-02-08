import logging
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy import or_
from sqlalchemy import update
from models.user import Caretaker, User
from models.organization import TwilioWhatsappTemplates, TemplateTypeEnum
from models.medication import Medication, MedicationStatus, MedicationLog
from core.database import SessionLocal
from sqlalchemy.orm import selectinload
from services.whatsapp_service import whatsapp_service
from tasks.utils import schedule_reminder_message
from models.organization import OrganizationAgents, AgentTypeEnum
from scripts.utils import convert_to_utc_datetime
from tasks.utils import schedule_reminder_message

logger = logging.getLogger(__name__)


def update_med_logs(user_id: int, medication_taken: bool, med_log_ids: list[int]):
    if not med_log_ids:
        return

    db = SessionLocal()
    try:
        status = (
            MedicationStatus.taken.value
            if medication_taken
            else MedicationStatus.missed.value
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
                    TwilioWhatsappTemplates.template_type == TemplateTypeEnum.medication_reminder.value,
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


def schedule_medication_reminders_for_day(db, today: datetime.date):
    try:
        active_medications = (
            db.query(Medication)
            .options(
                selectinload(Medication.times_of_day),
                selectinload(Medication.user),
            )
            .filter(
                or_(
                    Medication.start_date == None,
                    Medication.start_date <= today,
                ),
                or_(
                    Medication.end_date == None,
                    Medication.end_date >= today,
                )
            )
            .all()
        )
        user_reminders = {}
        agent_id_cache = {}
        for med in active_medications:
            try:
                user = med.user
                timezone = user.timezone
                preferred_reminder_channel = user.preferred_reminder_channel
                
                # Cache agent_id for organization to avoid redundant DB queries
                if user.organization_id not in agent_id_cache:
                    agent_id = db.query(OrganizationAgents).filter(OrganizationAgents.agent_type == AgentTypeEnum.medication_reminder.value, OrganizationAgents.organization_id == user.organization_id).first().agent_id
                    agent_id_cache[user.organization_id] = agent_id
                else:
                    agent_id = agent_id_cache[user.organization_id]

                payload = {
                    "user_info": {
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'phone_number': user.phone_number,
                        'language': user.preferred_consultation_language,
                        'user_id': user.id,
                        "agent_id": agent_id,
                        "preferred_reminder_channel": preferred_reminder_channel,
                    },
                    "medication_info": {}
                }

                if user.id not in user_reminders:
                    user_reminders[user.id] = payload

                for time in med.times_of_day:
                    med_time = time.time_of_day
                    dt_utc = convert_to_utc_datetime(tz_name = timezone, date=today, time=med_time)
                    if not dt_utc:
                        logger.error(f"Failed to convert time to UTC for user {user.id}, medication {med.id}, time {med_time}")
                        continue

                    med_payload = build_medication_payload(med, time)

                    if dt_utc not in user_reminders[user.id]["medication_info"]:
                        user_reminders[user.id]["medication_info"][dt_utc] = [med_payload]

                    else:
                        user_reminders[user.id]["medication_info"][dt_utc].append(med_payload)
            except Exception as e:
                logger.error(f"Error processing medication {med.id}: {e}")
                continue

        schedule_reminder_messages_for_users(user_reminders)

        logger.info(f"Scheduled medication reminders for {len(active_medications)} active medications.")
    except Exception as e:
        logger.error(f"Error scheduling medication reminders: {e}")


def build_medication_payload(medication_obj, time_obj):
    return {
        'medication_id': medication_obj.id,
        'medication_name': medication_obj.name,
        'medication_dosage': medication_obj.dosage,
        'medication_purpose': medication_obj.purpose,
        'time_of_day': time_obj.time_of_day.strftime("%H:%M"),
        'time_id': time_obj.id
    }

def schedule_reminder_messages_for_users(user_reminders):
    for user_id, info in user_reminders.items():
        try:
            preferred_reminder_channel = info['user_info']["preferred_reminder_channel"]
            for dt_utc, meds in info["medication_info"].items():
                schedule_reminder_message(
                    payload={
                        **user_reminders[user_id]["user_info"],
                        "medications": meds
                    },
                    dt_utc=dt_utc,
                    preferred_reminder_channel=preferred_reminder_channel,
                )
        except Exception as e:
            logger.error(f"Error scheduling reminders for user {user_id}: {e}")
            continue