import logging
from datetime import datetime, timezone
from scripts.utils import convert_local_time_to_utc_time, get_zoneinfo_safe
from sqlalchemy import Time, or_
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from models.user import User
from models.organization import TwilioWhatsappTemplates, TemplateTypeEnum
from models.medication import Medication, MedicationStatus, MedicationLog, MedicationTime
from core.database import SessionLocal
from sqlalchemy.orm import selectinload
from services.whatsapp_service import whatsapp_service
from tasks.utils import schedule_reminder_message
from models.organization import OrganizationAgents, AgentTypeEnum

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


def create_medication_logs(user_id, medications, status=MedicationStatus.unconfirmed.value):
    with SessionLocal() as db:
        med_log_ids = []
        for medication in medications:
            med_log = MedicationLog(
                medication_id=medication['medication_id'],
                medication_time_id=medication['time_id'],
                user_id=user_id,
                status=status
            )
            db.add(med_log)
            db.flush()
            med_log_ids.append(med_log.id)
        db.commit()
        return med_log_ids


def schedule_medication_reminders_for_hour(db, today: datetime.date, hour_start: Time, hour_end: Time):
    try:
        active_medications = (
            db.query(Medication)
            .join(MedicationTime)
            .options(
                selectinload(Medication.times_of_day),
                selectinload(Medication.user),
            )
            .filter(
                Medication.is_active.is_(True),
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
        count = 0
        user_reminders = {}
        agent_id_cache = {}
        for med in active_medications:
            try:
                scheduled_for_med = False
                user = med.user
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
                        "phone_number_id": user.organization.phone_number_id
                    },
                    "medication_info": {}
                }

                if user.id not in user_reminders:
                    user_reminders[user.id] = payload

                for time in med.times_of_day:
                    med_time = time.time_of_day
                    med_time_utc = convert_local_time_to_utc_time(med_time, user.timezone)
                    if not (hour_start <= med_time_utc < hour_end):
                        continue

                    dt_utc = datetime.combine(today, med_time_utc)
                    
                    
                    if time.scheduled_at and time.scheduled_at == dt_utc:
                        logger.info(f"Medication {med.id} for user {user.id} at time {med_time} has already been scheduled. Skipping duplicate scheduling.")
                        continue


                    med_payload = build_medication_payload(med, time)

                    if dt_utc not in user_reminders[user.id]["medication_info"]:
                        user_reminders[user.id]["medication_info"][dt_utc] = [med_payload]

                    else:
                        user_reminders[user.id]["medication_info"][dt_utc].append(med_payload)
                    
                    time.scheduled_at = dt_utc
                    db.add(time)
                    try:
                        db.commit()
                    except IntegrityError:
                        db.rollback()
                        logger.warning(f"MedicationTime with id {time.id} and scheduled_at {dt_utc} already exists.")
                        continue
                    scheduled_for_med = True

                if scheduled_for_med:
                    count += 1
                
            except Exception as e:
                logger.error(f"Error processing medication {med.id}: {e}")
                continue

        schedule_reminder_messages_for_users(user_reminders)

        logger.info(f"Scheduled medication reminders for {count} medications at {hour_start}-{hour_end}.")
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


def construct_medication_object_for_reminder(medication_list: list[dict]):
    """
    structure:
    [
        {
            "medication_id": 1,
            "time_id": 3
        },
        ...]
    """
    meds = []
    with SessionLocal() as db:
        if not medication_list:
            return meds
        
        med_ids = [m['medication_id'] for m in medication_list]
        time_ids = [m['time_id'] for m in medication_list]
        
        # Fetch all medications and times in bulk
        medications = db.query(Medication).filter(Medication.id.in_(med_ids)).all()
        times = db.query(MedicationTime).filter(MedicationTime.id.in_(time_ids)).all()
        
        # Create lookup dicts
        med_dict = {m.id: m for m in medications}
        time_dict = {t.id: t for t in times}
        
        for med_dict_item in medication_list:
            med_id = med_dict_item['medication_id']
            time_id = med_dict_item['time_id']
            med = med_dict.get(med_id)
            time_obj = time_dict.get(time_id)
            if med and time_obj:
                payload = build_medication_payload(med, time_obj)
                meds.append(payload)
    return meds


def construct_user_payload_for_reminder(user_id: int):
    with SessionLocal() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User not found for constructing reminder payload: {user_id}")
            return {}
        
        payload = {
            'first_name': user.first_name,
            'last_name': user.last_name,
            'phone_number': user.phone_number,
            'language': user.preferred_consultation_language,
            'user_id': user.id,
            "preferred_reminder_channel": user.preferred_reminder_channel
        }

        return payload