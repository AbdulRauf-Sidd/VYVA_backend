from celery import Celery
from core.config import settings
from celery.schedules import crontab

celery_app = Celery(
    settings.APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["tasks.management_tasks", "tasks.medication_tasks", "tasks.onboarding_tasks", "tasks.general_functions_tasks", "tasks.brain_coach_tasks"],  # import your tasks here
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "hourly-process-pending-onboarding-users": {
        "task": "process_pending_onboarding_users",
        "schedule": crontab(minute=0),  # runs every hour
        },
        "hourly-medication-reminder-scheduler": {
            "task": "schedule_calls_for_hour",
            "schedule": crontab(minute=0),  # runs every hour
        },
        "weekly-brain-coach-report-scheduler": {
            "task": "send_weekly_brain_coach_reports",
            # Fires once a week. Delivery lands at a different local hour
            # per user's timezone (some earlier, some later) - that's fine.
            "schedule": crontab(minute=0, hour=0, day_of_week="monday"),
        }
    }
)

# Optional: autoretry policy
celery_app.conf.task_annotations = {
    "*": {"max_retries": 1, "default_retry_delay": 60}
}

celery_app.conf.broker_transport_options = {
    'visibility_timeout': 108000,  # 30 hours in seconds
}
