import logging
from datetime import datetime, timezone

from sqlalchemy.orm import selectinload

from celery_app import celery_app
from core.database import SessionLocal
from models.organization import AgentTypeEnum, Organization
from models.user import User
from models.user_check_ins import ScheduledSession
from services.elevenlabs_service import make_general_reminder_call
from tasks.utils import schedule_celery_task_for_scheduled_session_status_check

logger = logging.getLogger(__name__)


@celery_app.task(name="fire_general_reminder", max_retries=0)
def fire_general_reminder(scheduled_session_id: int):
    with SessionLocal() as db:
        try:
            session = (
                db.query(ScheduledSession)
                .filter(ScheduledSession.id == scheduled_session_id)
                .first()
            )

            if not session:
                logger.error(f"[fire_general_reminder] ScheduledSession {scheduled_session_id} not found.")
                return

            if session.is_cancelled:
                logger.info(f"[fire_general_reminder] Session {scheduled_session_id} is cancelled — skipping.")
                return

            metadata = session.metadata_ or {}
            purpose = metadata.get("purpose", "")

            user = (
                db.query(User)
                .options(
                    selectinload(User.organization).selectinload(Organization.agents)
                )
                .filter(User.id == session.user_id)
                .first()
            )

            if not user:
                logger.error(f"[fire_general_reminder] User {session.user_id} not found.")
                return

            general_reminder_agent_id = None
            for agent in user.organization.agents:
                if agent.agent_type == AgentTypeEnum.general_reminder.value and agent.is_active:
                    general_reminder_agent_id = agent.agent_id
                    break

            if not general_reminder_agent_id:
                logger.error(f"[fire_general_reminder] No general_reminder agent found for organization {user.organization.id}.")
                return

            payload = {
                "user_id": user.id,
                "agent_id": general_reminder_agent_id,
                "first_name": user.first_name,
                "phone_number": user.phone_number,
                "language": user.preferred_consultation_language,
                "phone_number_id": user.organization.phone_number_id,
                "purpose": purpose,
            }

            response = make_general_reminder_call(payload)

            if response:
                call_sid = response.get("callSid")
                if call_sid:
                    session.call_sid = call_sid
                    db.commit()
                    schedule_celery_task_for_scheduled_session_status_check()
                else:
                    logger.error(f"[fire_general_reminder] Call initiated but no callSid returned for session {scheduled_session_id}.")
                    db.commit()
            else:
                logger.error(f"[fire_general_reminder] Call failed for session {scheduled_session_id}.")

        except Exception as e:
            db.rollback()
            logger.error(f"[fire_general_reminder] Error for session {scheduled_session_id}: {e}")
