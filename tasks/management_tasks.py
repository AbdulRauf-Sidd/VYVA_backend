from core.database import SessionLocal, get_sync_session
from celery_app import celery_app
from models import user
from services.elevenlabs_service import make_onboarding_call, make_medication_reminder_call, make_brain_coach_call, make_check_up_call, call_agent
from models.user import User
from models.onboarding import OnboardingUser, OnboardingLogs
from models.organization import Organization, OrganizationAgents, AgentTypeEnum, TwilioWhatsappTemplates, TemplateTypeEnum
import logging
from sqlalchemy.orm import selectinload, with_loader_criteria
from datetime import datetime
from sqlalchemy.orm import Session
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from models.medication import MedicationStatus
from sqlalchemy import or_, select
from models.eleven_labs_sessions import ElevenLabsSessions
from models.user_check_ins import ScheduledSession
from scripts.medication_utils import schedule_medication_reminders_for_day 
from models.user_check_ins import UserCheckin, CheckInType
from tasks.utils import schedule_celery_task_for_call_status_check, update_medication_status, schedule_check_in_calls_for_day, schedule_celery_task_for_scheduled_session_status_check

from scripts.onboarding_utils import construct_onboarding_user_payload
from scripts.utils import date_now_in_timezone, get_iso_language
from services.helpers import construct_user_not_picked_up_message

from twilio.rest import Client
from core.config import settings
from services.whatsapp_service import whatsapp_service

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
            .filter(OnboardingUser.onboarding_status == False, OnboardingUser.onboarding_call_scheduled == False, OnboardingUser.call_attempts < 3, OnboardingUser.consent_given.is_not(False))
            .all()
        )

        for user in pending_users:
            dt_today_utc = None
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
def update_call_status(self, payload=None, agent_type=None):
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
                    if agent_type == AgentTypeEnum.medication_reminder.value and payload:
                        update_medication_status(payload, MedicationStatus.unconfirmed.value)

                    if agent_type == AgentTypeEnum.check_in.value:
                        pass
                    
                    session.status = status
        db.commit()
    except Exception as e:
        logger.error(f"error updating call status: {e}")
    finally:
        db.close()


@celery_app.task(name="update_scheduled_call_status", bind=True)
def update_scheduled_call_status(self):
    db: Session = SessionLocal()
    try:
        excluded_statuses = ["answered"]
        query = (
            select(ScheduledSession).where(
                or_(
                    ScheduledSession.status.is_(None),
                    ScheduledSession.status.notin_(excluded_statuses),
                ),
                ScheduledSession.is_completed.is_(False),
            )
        )

        result = db.execute(query)
        sessions = result.scalars().all()

        for session in sessions:
            status = get_call_status_from_twilio(session.call_sid)
            status = status.get('status', None)
            session.status = status
            session_type = session.session_type
            if status in ["declined", "no_answer", "failed"]: #call completed
                # Mark medication as unconfirmed
                if session_type == CheckInType.check_up_call.value:
                    if session.attempts >= 3:
                        user_id = session.user_checkin.user_id
                        logger.info(f"User {user_id} has missed 3 check-up calls.")
                        send_emergency_alert_whatsapp.apply_async(args=[user_id])
                        call_emergency_outbound_agent.apply_async(args=[user_id])
                        # session.is_completed = True
                        session.completed_at = datetime.now(timezone.utc)
                    else:
                        initiate_check_up_call.apply_async(args=[session.user_checkin_id], countdown=60) #reschedule call after 5 minutes
            else:
                session.is_completed = True
                session.completed_at = datetime.now(timezone.utc)

        db.commit()
    except Exception as e:
        logger.error(f"error updating scheduled call status: {e}")
    finally:
        db.close()


@celery_app.task(name="send_emergency_alert_whatsapp")
def send_emergency_alert_whatsapp(user_id):
    with get_sync_session() as db:
        user = db.query(User).options(selectinload(User.caretaker)).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User not found for emergency alert: {user_id}")
            return
        
        if not user.caretaker:
            logger.error(f"Caretaker not found for user {user_id}, cannot send emergency alert")
            return
        
        caretaker_phone = user.caretaker.phone_number
        iso_language = get_iso_language(user.preferred_consultation_language)
        message = construct_user_not_picked_up_message(iso_language)
        
        content_variables = {
            "1": user.first_name,
            "2": message,
        }

        template_id = db.query(TwilioWhatsappTemplates.template_id).filter(TwilioWhatsappTemplates.language == user.preferred_consultation_language, TwilioWhatsappTemplates.template_type == TemplateTypeEnum.emergency_contact_alert.value).first()
        response = whatsapp_service.send_message_sync(
            to_phone=caretaker_phone,
            template_id=template_id,
            template_data=content_variables,
        )

        logger.info(f"Emergency alert WhatsApp response: {response}")

@celery_app.task(name="call_emergency_outbound_agent")
def call_emergency_outbound_agent(user_id):
    with get_sync_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        agent_result = db.query(OrganizationAgents).filter(
            OrganizationAgents.organization_id == user.organization.id,
            OrganizationAgents.agent_type == AgentTypeEnum.emergency_responder.value,
            OrganizationAgents.is_active == True
        ).first()
        agent_id = agent_result.agent_id if agent_result else None
        message = construct_user_not_picked_up_message(get_iso_language(user.preferred_consultation_language))
        payload = {
            "full_name": user.full_name,
            "address": user.full_address,
            "phone_number": user.phone_number,
            "emergency": message,
            "language": user.preferred_consultation_language or "spanish",
            "phone_number_id": user.organization.phone_number_id
        }
        response = call_agent(agent_id=agent_id, phone_number="+34664338991", payload=payload) #DUMMY
        logger.info(f"Emergency outbound agent response: {response}")

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
            "phone_number_id": user.organization.phone_number_id
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
    db = SessionLocal()
    try:
        user_checkin = (
            db.query(UserCheckin)
            .options(
                selectinload(UserCheckin.scheduled_sessions),
                selectinload(UserCheckin.user)
                .selectinload(User.organization)
                .selectinload(Organization.agents),
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
        for agent in agents:
            logger.info(agent.agent_type)
            if agent.agent_type == AgentTypeEnum.check_in.value:
                check_up_agent_id = agent.agent_id
                break
        if not check_up_agent_id:
            logger.error(f"No check-up agent found for organization {user.organization.id}")
            return

        payload = {
            "user_id": user.id,
            "agent_id": check_up_agent_id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number,
            "language": user.preferred_consultation_language,
            "address": user.full_address,
            "phone_number_id": user.organization.phone_number_id
        }

        if not last_pending_session:
            logger.warning(f"No pending session found for check in {check_in_id}")
            return
        
        response = make_check_up_call(payload)

        if response:
            last_pending_session.attempts += 1
            last_pending_session.call_sid = response.get('callSid')
            db.commit()
            schedule_celery_task_for_scheduled_session_status_check()

    except Exception as e:
        logger.error(f"Error initiating check-up call for check ID {check_in_id}: {e}")
    finally:
        db.close()
