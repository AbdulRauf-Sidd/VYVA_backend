from celery import Celery
from celery.schedules import crontab

# Minimal Celery configuration
celery_app = Celery(
    'vyva-celery',
    broker="memory://",
    backend="rpc://",
    include=['tasks']
)

# Basic configuration
celery_app.conf.update(
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    timezone='CET',
)

celery_app.conf.beat_schedule = {
    "check-medication-every-minute": {
        "task": "tasks.check_medication_time",
        "schedule": crontab(minute="*"),  # every minute
    },
}