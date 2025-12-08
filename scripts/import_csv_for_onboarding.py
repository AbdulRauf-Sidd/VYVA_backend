import csv
import logging
from pathlib import Path
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from models.onboarding import OnboardingUser
from schemas.onboarding_user import OnboardingUserCreate, OnboardingUserUpdate
from core.database import get_async_session  # <- your helper

logger = logging.getLogger(__name__)


async def import_onboarding_users_from_csv(file_path: str):
    """
    Reads users from a CSV file and updates or inserts into onboarding_users.
    You don’t need to pass a session; it’s handled internally.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    async with get_async_session() as db_session:
        try:
            with path.open("r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    first_name = (row.get("first_name") or "").strip() or None
                    last_name = (row.get("last_name") or "").strip() or None
                    email = (row.get("email") or "").strip().lower() or None
                    phone = (row.get("phone") or "").strip() or None
                    age = int(row["age"]) if row.get("age") else None

                    if not (email or phone):
                        logger.warning("Skipping row with no email/phone.")
                        continue

                    # Check for existing user
                    query = select(OnboardingUser).where(
                        (OnboardingUser.email == email) | (OnboardingUser.phone_number == phone)
                    )
                    result = await db_session.execute(query)
                    existing_user = result.scalar_one_or_none()

                    if existing_user:
                        # Update existing
                        update_data = OnboardingUserUpdate(
                            first_name=first_name,
                            last_name=last_name,
                            email=email,
                            phone_number=phone,
                            age=age,
                        )
                        for field, value in update_data.model_dump(exclude_unset=True).items():
                            setattr(existing_user, field, value)
                    else:
                        # Create new
                        new_user = OnboardingUserCreate(
                            first_name=first_name,
                            last_name=last_name,
                            email=email,
                            phone_number=phone,
                            age=age,
                        )
                        db_session.add(new_user)

                await db_session.commit()
                logger.info("CSV import completed successfully.")

        except SQLAlchemyError as e:
            await db_session.rollback()
            logger.exception(f"Database error during CSV import: {str(e)}")
            raise
        except Exception as e:
            await db_session.rollback()
            logger.exception(f"Unexpected error during CSV import: {str(e)}")
            raise
