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
from models.medication import Medication, MedicationTime, MedicationStatus
from models.organization import OrganizationAgents, AgentTypeEnum
from sqlalchemy import or_, select
from models.eleven_labs_sessions import ElevenLabsSessions

from tasks.utils import schedule_celery_task_for_call_status_check, schedule_reminder_message, update_medication_status

# from scripts.utils import construct_onboarding_user_payload

from twilio.rest import Client
from core.config import settings

logger = logging.getLogger(__name__)

twilio_client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

def get_call_status_from_twilio(callSid: str) -> dict:
    try:
        call = twilio_client.calls(callSid).fetch()
        raw = call.status

        mapping = {
            "completed": "answered",
            "busy": "declined",
            "no-answer": "no_answer",
            "canceled": "declined",
            "failed": "failed",
            "queued": "in_progress",
            "ringing": "in_progress",
            "in-progress": "in_progress",
        }

        normalized = mapping.get(raw, "unknown")

        FINAL = {"answered", "declined", "no_answer", "failed"}

        return {
            "raw_status": raw,
            "status": normalized,
            "is_final": normalized in FINAL,
        }
    except Exception as e:
        logger.error(f"Error fetching call status from Twilio for Call SID {callSid}: {e}")
        return {}

@celery_app.task(name="initiate_onboarding_call", max_retries=0)
def initiate_onboarding_call(payload: dict):
    try:
        db = SessionLocal()
        response = make_onboarding_call(payload)
        onboarding_record = db.query(OnboardingUser).filter(OnboardingUser.id == payload.get("user_id")).first()
        onboarding_record.onboarding_call_scheduled = False
        onboarding_record.call_attempts += 1
        onboarding_record.called_at = datetime.now()
        if not response:
            logger.error(f"Failed to initiate onboarding call for payload: {payload}")

        onboarding_log = OnboardingLogs(
            call_at=datetime.now(),
            call_id=response.get('callSid'),
            onboarding_user_id=onboarding_record.id,
            status="in_progress",
        )
        db.add(onboarding_record)
        db.add(onboarding_log)
        db.commit()
        schedule_celery_task_for_call_status_check()
    except Exception as e:
        logger.error(f"Error initiating onboarding call: {e}")
    finally:
        db.close()

    
@celery_app.task(name="process_pending_onboarding_users", max_retries=0)
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

        return {"status": 200, "count": len(pending_users)}

    except Exception as e:
        db.rollback()
        logger.error(f"Error processing pending onboarding users: {e}")
    finally:
        db.close()


@celery_app.task(name="schedule_calls_for_day", max_retries=0)
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
            agent_id = db.query(OrganizationAgents).filter(OrganizationAgents.agent_type == AgentTypeEnum.medication_reminder.value, OrganizationAgents.organization_id == user.organization_id).first().agent_id


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
                local_dt = datetime.combine(today, med_time, tzinfo=ZoneInfo(timezone))
                dt_utc = local_dt.astimezone(ZoneInfo("UTC"))
                dt_utc = dt_utc.replace(second=0, microsecond=0)


                med_payload = {
                    'medication_id': med.id,
                    'medication_name': med.name,
                    'medication_dosage': med.dosage,
                    'medication_purpose': med.purpose,
                    'time_of_day': med_time.strftime("%H:%M"),
                    'time_id': time.id
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
                    dt_utc=dt_utc,
                    preferred_reminder_channel=preferred_reminder_channel,
                )
        
        logger.info(f"Scheduled medication reminders for {len(active_medications)} active medications.")
        
        ### schedule check in calls. .. to be implemented TODO

    except Exception as e:
        db.rollback()
        logger.exception(f"Error scheduling calls for day: {e}")
    finally:
        db.close()

@celery_app.task(name="initiate_medication_reminder_call")
def initiate_medication_reminder_call(payload):
    response = make_medication_reminder_call(payload)
    if response:
        call_sid = response.get('callSid')
        db: Session = SessionLocal()
        try:
            session_record = ElevenLabsSessions(
                user_id=payload.get('user_id'),                 # make sure this exists
                agent_id=payload.get("agent_id"),
                call_sid=call_sid,
                status="ringing"
            )

            db.add(session_record)
            db.commit()
            # db.refresh(session_record)
            schedule_celery_task_for_call_status_check(payload)
        
        except Exception as e:
            logger.error(f"error creating eleven labs session record: {e}")

        finally:
            db.close()

@celery_app.task(name="update_call_status", bind=True)
def update_call_status(self, payload=None):
    db: Session = SessionLocal()
    try:
        excluded_statuses = ["answered", "declined", "no_answer", "failed"]
        query = (
            select(ElevenLabsSessions)
            .where(
                ElevenLabsSessions.call_sid.isnot(None),
                ElevenLabsSessions.status.notin_(excluded_statuses)
            )
        )

        result = db.execute(query)
        sessions = result.scalars().all()

        for session in sessions:
            status = get_call_status_from_twilio(session.call_sid)
            if status in excluded_statuses: #call completed
                if status in ["declined", "no_answer", "failed"]:
                    # Mark medication as unconfirmed
                    if payload:
                        update_medication_status(payload, MedicationStatus.unconfirmed.value)
                    
                    session.status = status
        db.commit()
    except Exception as e:
        logger.error(f"error updating call status: {e}")
    finally:
        db.close()


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



@celery_app.task(name="check_onboarding_call_status")
def check_onboarding_call_status():
    db = SessionLocal()
    try:
        pending_logs = (
            db.query(OnboardingLogs)
            .filter(
                or_(
                    OnboardingLogs.status.is_(None),
                    OnboardingLogs.status == "in_progress",
                )
            )
            .all()
        )
        updated = False
        for log in pending_logs:
            call_sid = log.call_id
            
            status_data = get_call_status_from_twilio(call_sid)
            status = status_data.get("status", None)

            if status:
                log.status = status
                updated = True

                db.add(log)

        if updated:
            db.commit()
                
    except Exception as e:
        db.rollback()
        logger.error(f"Error checking onboarding call status: {e}")

    finally:
        db.close()