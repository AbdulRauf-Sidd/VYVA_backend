from core.database import SessionLocal
from celery_app import celery_app
from models import user
from services.elevenlabs_service import make_onboarding_call, make_medication_reminder_call
from models.user import User
from models.onboarding import OnboardingUser, OnboardingLogs
import logging
from sqlalchemy.orm import selectinload
from datetime import datetime
from sqlalchemy.orm import Session
from datetime import datetime, date
from zoneinfo import ZoneInfo
from models.medication import Medication, MedicationTime
from models.organization import OrganizationAgents, AgentTypeEnum
from sqlalchemy import or_

from tasks.utils import schedule_reminder_message

# from scripts.utils import construct_onboarding_user_payload

from twilio.rest import Client
from core.config import settings

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

def get_call_status_from_twilio(callSid: str) -> dict:
    call = twilio_client.calls(callSid).fetch()
    raw = call.status

    mapping = {
        "completed": "answered",
        "busy": "declined",
        "no-answer": "not_available",
        "canceled": "declined",
        "failed": "failed",
        "queued": "in_progress",
        "ringing": "in_progress",
        "in-progress": "in_progress",
    }

    normalized = mapping.get(raw, "unknown")

    FINAL = {"answered", "declined", "not_available", "failed"}

    return {
        "raw_status": raw,
        "status": normalized,
        "is_final": normalized in FINAL,
    }

logger = logging.getLogger(__name__)

@celery_app.task(name="initiate_onboarding_call")
def initiate_onboarding_call(payload: dict):
    db = SessionLocal()
    try:
        response = make_onboarding_call(**payload)

        if not response:
            logger.error(f"Failed to initiate onboarding call for payload: {payload}")
            return

        onboarding_record = (
            db.query(OnboardingUser)
            .filter(OnboardingUser.id == payload.get("user_id"))
            .first()
        )

        if onboarding_record:
            onboarding_record.onboarding_call_scheduled = False
            onboarding_record.call_attempts += 1
            onboarding_record.called_at = datetime.utcnow()
            db.commit()

    except Exception as e:
        db.rollback()
        logger.exception("Celery onboarding task failed")
        raise
    finally:
        db.close()
    
@celery_app.task(name="process_pending_onboarding_users")
def process_pending_onboarding_users():
    db = SessionLocal()
    try:
        pending_users = (
            db.query(OnboardingUser)
            .options(selectinload(OnboardingUser.organization))
            .filter(OnboardingUser.onboarding_status == False, OnboardingUser.onboarding_call_scheduled == False, OnboardingUser.call_attempts < 3)
            .all()
        )

        for user in pending_users:

            preferred_time = user.preferred_time
            if preferred_time:
                dt_today_utc = datetime.combine(date.today(), preferred_time, tzinfo=ZoneInfo("UTC"))
            else:
                default_time = datetime.strptime("09:00", "%H:%M").time()
                local_dt = datetime.combine(date.today(), default_time, tzinfo=ZoneInfo(user.timezone))
                dt_today_utc = local_dt.astimezone(ZoneInfo("UTC"))

            full_address = ""

            if user.address:
                full_address = user.address
            if user.city_state_province:
                full_address += f", {user.city_state_province}"
            if user.postal_zip_code:
                full_address += f", {user.postal_zip_code}"

            if not full_address:
                full_address = "Not Available"

            payload = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone_number': user.phone_number,
                'language': user.language,
                'user_id': user.id,
                'agent_id': user.organization.onboarding_agent_id,
                'address': full_address,
                'user_type': user.preferred_communication_channel,
                'caregiver_name': user.caregiver_name,
                'caregiver_phone': user.caregiver_contact_number,
            }

            # payload = construct_onboarding_user_payload(user, user.organization.onboarding_agent_id)

            celery_app.send_task(
                "initiate_onboarding_call",
                args=[payload,],
                eta=dt_today_utc
            )

            user.onboarding_call_scheduled = True
            db.add(user)
            db.commit()

        return {"status": "ok", "count": len(pending_users)}

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()


@celery_app.task(name="schedule_calls_for_day")
def schedule_calls_for_day():
    db = SessionLocal()
    try:
        today = date.today()
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

        for med in active_medications:
            user = med.user
            timezone = user.timezone
            preferred_reminder_channel = user.preferred_reminder_channel
            print('org', user.organization_id)
            agent_id = db.query(OrganizationAgents).filter(OrganizationAgents.agent_type == AgentTypeEnum.MEDICATION_REMINDER, OrganizationAgents.organization_id == user.organization_id).first().agent_id


            payload = {
                "user_info": {
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'phone_number': user.phone_number,
                    'language': user.language,
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
                local_dt = datetime.combine(today, med_time, tzinfo=ZoneInfo(timezone))
                dt_utc = local_dt.astimezone(ZoneInfo("UTC"))
                dt_utc = dt_utc.replace(second=0, microsecond=0)


                med_payload = {
                    'medication_name': med.name,
                    'medication_dosage': med.dosage,
                    'medication_purpose': med.purpose,
                    'time_of_day': med_time.strftime("%H:%M"),
                }               

                if dt_utc not in user_reminders[user.id]["medication_info"]:
                    user_reminders[user.id]["medication_info"][dt_utc] = [med_payload]
                    
                else:
                    user_reminders[user.id]["medication_info"][dt_utc].append(med_payload)

                # schedule_reminder_message(payload, dt_utc, preferred_reminder_channel, agent_id)

        for user_id, info in user_reminders.items():
            preferred_reminder_channel = info['user_info']["preferred_reminder_channel"]
            for dt_utc, meds in info["medication_info"].items():
                schedule_reminder_message(
                    payload={
                        **user_reminders[user_id]["user_info"],
                        "medications": meds
                    },
                    scheduled_time=dt_utc,
                    channel=preferred_reminder_channel,
                )
        
        logger.info(f"Scheduled medication reminders for {len(active_medications)} active medications.")
        
        ### schedule check in calls. .. to be implemented TODO

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()

@celery_app.task(name="initiate_medication_reminder_call")
def initiate_medication_reminder_call(payload):
    response = make_medication_reminder_call(payload)
    
    payload['callSid'] = response.get('callSid')
    
    check_call_status_and_save.apply_async(
        args=[payload],
        countdown=60,
    )

@celery_app.task(name="check_call_status_and_save", bind=True)
def check_call_status_and_save(self, payload: dict):
    logger.info(f"Twilio status for call {payload}: ")
    db: Session = SessionLocal()
    try:
        call_sid = payload.get("callSid")
        user_id = payload.get("user_id")
        phone_number = payload.get("phone_number")

        user = None
        if user_id:
            user = db.query(OnboardingUser).filter(OnboardingUser.id == user_id).first()
        if not user and phone_number:
            user = db.query(OnboardingUser).filter(OnboardingUser.phone_number == phone_number).first()

        if not user:
            user = OnboardingUser(
                id=user_id,
                first_name=payload.get("first_name"),
                last_name=payload.get("last_name"),
                phone_number=phone_number,
                language=payload.get("language"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            logger.info(f"Created new user with ID {user.id} and phone {user.phone_number}")

        status_data = get_call_status_from_twilio(call_sid)
        logger.info(f"Call SID: {call_sid}, Status Data: {status_data}")

        log_entry = OnboardingLogs(
            call_at=datetime.now(),
            call_id=call_sid,
            onboarding_user_id=user.id,
            summary=f"Call status: {status_data.get('status')}, raw status: {status_data.get('raw_status')}"
        )
        db.add(log_entry)
        db.commit()
        logger.info(f"Saved onboarding log for user {user.id} and call {call_sid}")

    except Exception as e:
        db.rollback()
        logger.error(f"Error saving onboarding log or creating user: {e}")
        raise

    finally:
        db.close()