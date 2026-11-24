from datetime import datetime, timezone

from sqlalchemy import select

from celery_app import celery_app
from core.database import SessionLocal
from core.logging import get_logger
from models.manual_calls import ManualCall
from models.user import User
from models.organization import OrganizationAgents, AgentTypeEnum
from services.elevenlabs_service import call_agent, track_agent_call
from services.helpers import construct_user_dynamic_variables
from tasks.utils import schedule_celery_task_for_call_status_check

logger = get_logger(__name__)


def build_manual_call_payload(user: User, agent_id: str) -> dict:
    """Same dynamic variables as the other outbound calls to a user."""
    payload = {
        "user_id": user.id,
        "agent_id": agent_id,
        "first_name": user.first_name,
        "phone_number": user.phone_number,
        "language": user.preferred_consultation_language or "english",
        "phone_number_id": user.organization.phone_number_id if user.organization else None,
    }
    return {**construct_user_dynamic_variables(user), **payload}


def find_main_agent_id(db, organization_id):
    agent = db.execute(
        select(OrganizationAgents).where(
            OrganizationAgents.organization_id == organization_id,
            OrganizationAgents.agent_type == AgentTypeEnum.main_agent.value,
            OrganizationAgents.is_active.is_(True),
        )
    ).scalars().first()
    return agent.agent_id if agent else None


def _place(db, call: ManualCall):
    user = db.get(User, call.user_id)
    if not user or not user.phone_number:
        raise ValueError("User or phone number not found")
    agent_id = call.agent_id or find_main_agent_id(db, user.organization_id)
    if not agent_id:
        raise ValueError(f"No active main_agent for organization {user.organization_id}")
    call.agent_id = agent_id
    call.phone_number = user.phone_number

    payload = build_manual_call_payload(user, agent_id)
    response = call_agent(
        agent_id=agent_id,
        phone_number=user.phone_number,
        payload=payload,
        first_message=call.override_first_message,
        system_prompt=call.override_prompt,
    )
    call.conversation_id = response.get("conversation_id")
    call.status = "placed"
    call.placed_at = datetime.now(timezone.utc)
    track_agent_call(user.id, agent_id, AgentTypeEnum.main_agent.value, payload, response)


@celery_app.task(name="dispatch_due_manual_calls")
def dispatch_due_manual_calls():
    """Runs every minute: claim due scheduled calls and place them."""
    db = SessionLocal()
    try:
        due = db.execute(
            select(ManualCall)
            .where(ManualCall.status == "scheduled", ManualCall.scheduled_at <= datetime.now(timezone.utc))
            .order_by(ManualCall.scheduled_at)
            .limit(50)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        for call in due:
            call.status = "queued"  # claimed, so another worker won't pick it up
        db.commit()

        placed_any = False
        for call in due:
            try:
                _place(db, call)
                placed_any = True
            except Exception as e:
                logger.error(f"Manual call {call.id} failed: {e}")
                call.status = "failed"
                call.error = str(e)[:1000]
            db.commit()

        if placed_any:
            schedule_celery_task_for_call_status_check()
    except Exception as e:
        logger.error(f"dispatch_due_manual_calls error: {e}")
        db.rollback()
    finally:
        db.close()
