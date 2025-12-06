from core.database import SessionLocal
from celery_app import celery_app
from services.elevenlabs_service import make_onboarding_call
from models.user import User
from models.onboarding_user import OnboardingUser
import logging

logger = logging.getLogger(__name__)
from services.elevenlabs_service import make_onboarding_call

@celery_app.task(name="initiate_onboarding_call")
def initiate_onboarding_call(payload: dict):
    response = make_onboarding_call(payload)
    logger.info(f"Initiate onboarding call response: {response}")
    # try:
    #     errors = validate_csv(file_content)
    #     if errors:
    #         return {"status": "error", "errors": errors}
        
    #     # Dummy ORM operation
    #     new_user = User(first_name="Test", last_name="Celery")
    #     db.add(new_user)
    #     db.commit()
    #     return {"status": "success", "message": "File processed and data saved."}
    # except Exception as e:
    #     db.rollback()
    #     raise e
    # finally:
    #     db.close()
    
@celery_app.task(name="process_pending_onboarding_users")
def process_pending_onboarding_users():

    db = SessionLocal()

    try:
        pending_users = (
            db.query(OnboardingUser)
            .filter(OnboardingUser.onboarding_status == False)
            .all()
        )

        print(f"[Celery] Found {len(pending_users)} pending onboarding users.")

        for user in pending_users:
            payload = {
                "user_id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone_number": user.phone_number,
                "email": user.email,
                "language": user.language,
                "preferred_time": str(user.preferred_time) if user.preferred_time else None,
                "timezone": user.timezone,
                "preferred_communication_channel": user.preferred_communication_channel,
                "land_line": user.land_line,
                "whatsapp_reports": user.whatsapp_reports,
                "organization_id": user.organization_id,
            }

            # Schedule onboarding call task
            celery_app.send_task(
                "initiate_onboarding_call",
                args=[payload],
            )

            print(f"[Celery] Assigned onboarding task for user {user.id}")

        return {"status": "ok", "count": len(pending_users)}

    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
