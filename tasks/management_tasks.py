from core.database import SessionLocal
import celery_app

@celery_app.task(name="initiate_onboarding_call")
def initiate_onboarding_call(self, user_id: int):
    db = SessionLocal()
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