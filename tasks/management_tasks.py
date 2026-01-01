from core.database import SessionLocal
from celery_app import celery_app
from models import user
from services.elevenlabs_service import make_onboarding_call, make_medication_reminder_call
from models.user import User
from models.onboarding import OnboardingUser, OnboardingLogs
import logging
from sqlalchemy.orm import selectinload
from datetime import datetime, date
from zoneinfo import ZoneInfo
from models.medication import Medication, MedicationTime
from models.organization import OrganizationAgents, AgentTypeEnum
# from sqlalchemy.orm import selectinload
from sqlalchemy import or_

from tasks.utils import schedule_reminder_message

# from scripts.utils import construct_onboarding_user_payload

logger = logging.getLogger(__name__)

@celery_app.task(name="initiate_onboarding_call")
def initiate_onboarding_call(payload: dict):
    db = SessionLocal()
    response = make_onboarding_call(payload)
    if not response:
        logger.error(f"Failed to initiate onboarding call for payload: {payload}")
    else:
        onboarding_record = db.query(OnboardingUser).filter(OnboardingUser.id == payload.get("user_id")).first()
        if onboarding_record:
            onboarding_record.onboarding_call_scheduled = False
            onboarding_record.call_attempts += 1
            onboarding_record.called_at = datetime.now()
            db.add(onboarding_record)
            db.commit()

    
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

@celery_app.task(name="check_call_status_and_save")
def check_call_status_and_save(payload: dict):
    db = SessionLocal()
    call_sid = payload.get("call_sid")

    try:
        status = make_onboarding_call({
            "check_status": True,
            "call_sid": call_sid
        })

        FINAL_STATUSES = {"answered", "declined", "completed", "failed", "busy"}

        if status and status.get("status") in FINAL_STATUSES:
            log = (
                db.query(OnboardingLogs)
                .filter(OnboardingLogs.call_sid == call_sid)
                .first()
            )

            if log:
                log.call_status = status.get("status")
                log.call_completed = True
                log.completed_at = datetime.now(ZoneInfo("UTC"))
                db.commit()

            return {"status": "completed"}

        initiate_medication_reminder_call.delay(payload)

        check_call_status_and_save.apply_async(
            args=[payload],
            countdown=300,
        )

        return {"status": "retrying"}

    except Exception:
        db.rollback()
        logger.exception("Call status check failed")
        raise
    finally:
        db.close()