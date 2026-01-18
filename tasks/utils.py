from celery_app import celery_app
from core.redis import conn, ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY, MEDICATION_REMINDER_CALL_STATUS_CHECK_REDIS_KEY
from models.medication import MedicationLog
import logging
from core.database import SessionLocal

logger = logging.getLogger(__name__)

def schedule_reminder_message(payload, dt_utc, preferred_reminder_channel):
    print(payload, dt_utc, preferred_reminder_channel)
    if preferred_reminder_channel:
        if preferred_reminder_channel == "whatsapp":
            celery_app.send_task(
                "send_whatsapp_medication_reminder",
                args=[payload,],
                eta=dt_utc
            )
        elif preferred_reminder_channel == "phone":
            celery_app.send_task(
                "initiate_medication_reminder_call",
                args=[payload,],
                eta=dt_utc
            )
        elif preferred_reminder_channel == "app":
            celery_app.send_task(
                "send_app_medication_reminder",
                args=[payload,],
                eta=dt_utc
            )
        else:
            # Default to WhatsApp
            celery_app.send_task(
                "send_whatsapp_medication_reminder",
                args=[payload,],
                eta=dt_utc
            )


def schedule_celery_task_for_call_status_check(payload=None):
    if payload:
        exists = conn.get(MEDICATION_REMINDER_CALL_STATUS_CHECK_REDIS_KEY)
        if not exists:
            celery_app.send_task(
                "update_call_status",
                args=[payload,],
                countdown=300 # 5 minutes
            )
            conn.set(MEDICATION_REMINDER_CALL_STATUS_CHECK_REDIS_KEY, 1, ex=300)    
    else:
        exists = conn.get(ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY)
    if not exists:
        celery_app.send_task(
            "check_onboarding_call_status",
            countdown=300  # 5 minutes
        )
        conn.set(ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY, 1, ex=300)  # Key expires in 5 minutes


def update_medication_status(payload, status):
    db = SessionLocal()
    try:
        medications = payload.get('medications')
        for medication in medications:
            medication_log = MedicationLog(
                user_id=payload.get('user_id'), 
                medication_id = medication.get('medication_id'),
                medication_time_id = medication.get('time_id'),
                status=status,
            )

            db.add(medication_log)
        
        db.commit()
    except Exception as e:
        logger.error(f"error marking medication as missed: {e}")
    finally:
        db.close()