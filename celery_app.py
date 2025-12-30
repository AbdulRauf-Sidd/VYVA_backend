from celery import Celery
from core.config import settings
from celery.schedules import crontab

celery_app = Celery(
    settings.APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.management_tasks"],  # import your tasks here
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "daily-process-pending-onboarding-users": {
        "task": "process_pending_onboarding_users",
        "schedule": crontab(hour=0, minute=0),  # runs daily at 12 AM
        },
        "daily-medication-reminder-scheduler": {
            "task": "schedule_calls_for_day",
            "schedule": crontab(hour=2, minute=22),  
        }
    }
)

# Optional: autoretry policy
celery_app.conf.task_annotations = {
    "*": {"max_retries": 3, "default_retry_delay": 5}
}

# celery_app.conf.beat_schedule = {
#     "daily-process-pending-onboarding-users": {
#         "task": "process_pending_onboarding_users",
#         "schedule": crontab(hour=0, minute=0),  # runs daily at 12 AM
#     },
#     "daily-medication-reminder-scheduler": {
#         "task": "schedule_calls_for_day",
#         "schedule": crontab(hour=1, minute=43),  
#     }
# }