from core.database import SessionLocal
from celery_app import celery_app
from services.elevenlabs_service import make_onboarding_call
from models.user import User
from models.onboarding import OnboardingUser, OnboardingLogs
import logging
from sqlalchemy.orm import selectinload
from datetime import datetime, date
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)
from services.elevenlabs_service import make_onboarding_call

@celery_app.task(name="initiate_onboarding_call")
def initiate_onboarding_call(payload: dict):
    db = SessionLocal()
    response = make_onboarding_call(payload)
    if not response:
        logger.error(f"Failed to initiate onboarding call for payload: {payload}")
    else:
        onboarding_record = db.query(OnboardingUser).filter(OnboardingUser.id == payload.get("user_id")).first()
        if onboarding_record:
            onboarding_record.onboarding_call_scheduled = True
            db.add(onboarding_record)
            db.commit()

    
@celery_app.task(name="process_pending_onboarding_users")
def process_pending_onboarding_users():
    db = SessionLocal()
    try:
        pending_users = (
            db.query(OnboardingUser)
            .options(selectinload(OnboardingUser.organization))
            .filter(OnboardingUser.onboarding_status == False, OnboardingUser.onboarding_call_scheduled == False)
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

            payload = {
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": user.phone_number,
                "language": user.language,
                "user_type": user.preferred_communication_channel,
                "agent_id": user.organization.onboarding_agent_id
            }

            celery_app.send_task(
                "initiate_onboarding_call",
                args=[payload],
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
