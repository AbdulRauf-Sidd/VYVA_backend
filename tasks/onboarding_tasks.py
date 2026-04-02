from services.google_places_service import get_geocode_address
from core.database import get_sync_session
from models.user import User
from celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="set_location_coordinates", bind=True, max_retries=3, default_retry_delay=1800)
def set_location_coordinates(self, user_id: int, location: str):
    try:
        response = get_geocode_address(location)
        if response:
            with get_sync_session() as db:
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    user.latitude = response['lat']
                    user.longitude = response['lng']
                    user.address = response['formatted_address']
                    db.commit()
                else:
                    logger.error(f"User with id {user_id} not found when setting location coordinates.")
        else:
            raise ValueError(f"Failed to geocode address for user {user_id}")
    except Exception as exc:
        logger.exception(f"Error setting location coordinates for user {user_id}")
        raise self.retry(exc=exc, countdown=1800)
