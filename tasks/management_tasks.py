from core.database import SessionLocal
from celery_app import celery_app
from services.elevenlabs_service import make_onboarding_call
from models.user import User
import logging

logger = logging.getLogger(__name__)

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