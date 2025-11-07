from celery import Celery
from core.config import settings

celery_app = Celery(
    settings.APP_NAME,
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.tasks.management_tasks"],  # import your tasks here
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Optional: autoretry policy
celery_app.conf.task_annotations = {
    "*": {"max_retries": 3, "default_retry_delay": 5}
}
