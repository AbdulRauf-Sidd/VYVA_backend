from core.database import SessionLocal
from celery_app import celery_app
from models import user
from services.elevenlabs_service import make_onboarding_call, make_medication_reminder_call, make_brain_coach_call, make_check_up_call
from models.user import User
from models.onboarding import OnboardingUser, OnboardingLogs
from models.organization import Organization, OrganizationAgents, AgentTypeEnum
import logging
from sqlalchemy.orm import selectinload, with_loader_criteria
from datetime import datetime
from sqlalchemy.orm import Session
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from models.medication import MedicationStatus
from sqlalchemy import or_, select
from models.eleven_labs_sessions import ElevenLabsSessions
from scripts.medication_utils import schedule_medication_reminders_for_day 
from models.user_check_ins import UserCheckin, CheckInType
from tasks.utils import schedule_celery_task_for_call_status_check, update_medication_status, schedule_check_in_calls_for_day

from scripts.onboarding_utils import construct_onboarding_user_payload
from scripts.utils import date_now_in_timezone

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
            .filter(OnboardingUser.onboarding_status == False, OnboardingUser.onboarding_call_scheduled == False, OnboardingUser.call_attempts < 3, OnboardingUser.consent_given != False)
            .all()
        )

        for user in pending_users:
            call_back_date_time = user.call_back_date_time
            if call_back_date_time: #check if the user has call back time that is later than today 
                user_today = date_now_in_timezone(user.timezone)
                callback_local_date = call_back_date_time.astimezone(
                    ZoneInfo(user.timezone)
                ).date()

                if callback_local_date > user_today:
                    continue
                
                dt_today_utc = call_back_date_time

            if not dt_today_utc:
                preferred_time = user.preferred_time
                if preferred_time:
                    dt_today_utc = datetime.combine(date.today(), preferred_time, tzinfo=ZoneInfo("UTC"))
                else:
                    default_time = datetime.strptime("09:00", "%H:%M").time()
                    local_dt = datetime.combine(date.today(), default_time, tzinfo=ZoneInfo(user.timezone))
                    dt_today_utc = local_dt.astimezone(ZoneInfo("UTC"))

            payload = construct_onboarding_user_payload(user, user.organization.onboarding_agent_id)

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
    try:
        db = SessionLocal()
        today = date.today()
        schedule_medication_reminders_for_day(db, today)
        schedule_check_in_calls_for_day(db, today)

    except Exception as e:
        logger.error(f"Error scheduling calls for the day: {e}")
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


@celery_app.task(name="initiate_brain_coach_session")
def initiate_brain_coach_session(check_in_id: int):
    db = SessionLocal()
    try:
        user_checkin = (
            db.query(UserCheckin)
            .options(
                selectinload(UserCheckin.scheduled_sessions),
                selectinload(UserCheckin.user)
                .selectinload(User.organization)
                .selectinload(Organization.agents),

                # with_loader_criteria(
                #     OrganizationAgents,   
                #     OrganizationAgents.agent_type == AgentTypeEnum.brain_coach.value,  # filter for brain coach agents
                #     include_aliases=True
                # )
            )
            .filter(UserCheckin.id == check_in_id)
            .first()
        )
        if not user_checkin:
            logger.error(f"UserCheckin not found for check_in_id {check_in_id}")
            return
        user = user_checkin.user
        last_pending_session = max(
            (s for s in user_checkin.scheduled_sessions if not s.is_completed and s.session_type == CheckInType.brain_coach.value),
            key=lambda s: s.scheduled_at,
            default=None
        )

        brain_coach_agent_id = None
        agents = user.organization.agents
        for agent in agents:
            logger.info(agent.agent_type)
            if agent.agent_type == AgentTypeEnum.brain_coach.value:
                brain_coach_agent_id = agent.agent_id
                break
        
        if not brain_coach_agent_id:
            logger.error(f"No brain coach agent found for organization {user.organization.id}")
            return

        
        payload = {
            "user_id": user.id,
            "agent_id": brain_coach_agent_id,
            "first_name": user.first_name,
            "phone_number": user.phone_number,
            "language": user.preferred_consultation_language,
        }
        
        response = make_brain_coach_call(payload)
        if not last_pending_session:
            logger.warning(f"No pending session found for check in {check_in_id}")
            return
        
        if response:
            last_pending_session.completed_at = datetime.now(timezone.utc)
            last_pending_session.is_completed = True
            db.commit()

        
    except Exception as e:
        logger.error(f"Error initiating brain coach session for check ID {check_in_id}: {e}")
    finally:
        db.close()

@celery_app.task(name="initiate_check_up_call")
def initiate_check_up_call(check_in_id: int):
    # Similar structure to initiate_brain_coach_session but with differences in payload and agent selection
    db = SessionLocal()
    try:
        user_checkin = (
            db.query(UserCheckin)
            .options(
                selectinload(UserCheckin.scheduled_sessions),
                selectinload(UserCheckin.user)
                .selectinload(User.organization)
                .selectinload(Organization.agents),
                # with_loader_criteria(
                #     OrganizationAgents,
                #     OrganizationAgents.agent_type == AgentTypeEnum.main_agent.value,
                #     include_aliases=True,
                # ),
            )
            .filter(UserCheckin.id == check_in_id)
            .first()
        )
        if not user_checkin:
            logger.error(f"UserCheckin not found for check_in_id {check_in_id}")
            return

        user = user_checkin.user
        last_pending_session = max(
            (s for s in user_checkin.scheduled_sessions if not s.is_completed and s.session_type == CheckInType.check_up_call.value),
            key=lambda s: s.scheduled_at,
            default=None,
        )

        check_up_agent_id = None
        agents = user.organization.agents
        print(agents)
        for agent in agents:
            logger.info(agent.agent_type)
            if agent.agent_type == AgentTypeEnum.main_agent.value:
                check_up_agent_id = agent.agent_id
                break
        if not check_up_agent_id:
            logger.error(f"No check-up agent found for organization {user.organization.id}")
            return

        payload = {
            "user_id": user.id,
            "agent_id": check_up_agent_id,
            "first_name": user.first_name,
            "phone_number": user.phone_number,
            "language": user.preferred_consultation_language,
        }

        response = make_check_up_call(payload)
        if not last_pending_session:
            logger.warning(f"No pending session found for check in {check_in_id}")
            return

        if response:
            last_pending_session.completed_at = datetime.now(timezone.utc)
            last_pending_session.is_completed = True
            db.commit()

    except Exception as e:
        logger.error(f"Error initiating check-up call for check ID {check_in_id}: {e}")
    finally:
        db.close()
