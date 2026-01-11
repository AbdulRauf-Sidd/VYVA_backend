from celery_app import celery_app
from core.redis import conn, ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY


def schedule_reminder_message(payload, dt_utc, preferred_reminder_channel):
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


def schedule_celery_task_for_call_status_check():
    exists = conn.get(ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY)
    if not exists:
        celery_app.send_task(
            "check_onboarding_call_status",
            countdown=300  # 5 minutes
        )
        conn.set(ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY, 1, ex=600)  # Key expires in 10 minutes