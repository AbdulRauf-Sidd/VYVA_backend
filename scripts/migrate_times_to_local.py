import logging
from sqlalchemy.orm import selectinload
from core.database import get_sync_session
from scripts.utils import convert_utc_time_to_local_time, get_zoneinfo_safe
from models.user import User
from models.medication import Medication
from models.user_check_ins import UserCheckin

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def migrate_medication_times_to_local():
    """Convert all medication_times.time_of_day values from UTC to the user's local time."""
    with get_sync_session() as db:
        users = db.query(User).options(
            selectinload(User.medications).selectinload(Medication.times_of_day)
        ).all()

        updated = 0
        skipped = 0

        for user in users:
            if not user.timezone:
                logger.warning(f"Skipping user {user.id} because timezone is missing")
                skipped += 1
                continue

            for medication in user.medications:
                for med_time in medication.times_of_day:
                    if not med_time.time_of_day:
                        continue
                    old_time = med_time.time_of_day
                    new_time = convert_utc_time_to_local_time(old_time, user.timezone)
                    if new_time and new_time != old_time:
                        med_time.time_of_day = new_time
                        updated += 1

        db.commit()
        logger.info(
            f"Medication time migration completed: {updated} values updated, {skipped} users skipped."
        )


def migrate_checkin_times_to_local():
    """Convert all user_checkins.check_in_time values from UTC to the user's local time."""
    with get_sync_session() as db:
        users = db.query(User).options(selectinload(User.user_checkins)).all()

        updated = 0
        skipped = 0

        for user in users:
            if not user.timezone:
                logger.warning(f"Skipping user {user.id} because timezone is missing")
                skipped += 1
                continue

            for checkin in user.user_checkins:
                if not checkin.check_in_time:
                    continue
                old_time = checkin.check_in_time
                new_time = convert_utc_time_to_local_time(old_time, user.timezone)
                if new_time and new_time != old_time:
                    checkin.check_in_time = new_time
                    updated += 1

        db.commit()
        logger.info(
            f"Check-in time migration completed: {updated} values updated, {skipped} users skipped."
        )