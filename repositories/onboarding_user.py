import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError

from models.onboarding import OnboardingUser
from schemas.onboarding_user import OnboardingUserCreate, OnboardingUserUpdate, OnboardingUserRead

logger = logging.getLogger(__name__)


class OnboardingUserRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    # --- CREATE (you already have this) ---
    async def create_user(self, user_data: OnboardingUserCreate) -> OnboardingUserRead:
        try:
            new_user = OnboardingUser(**user_data.model_dump())
            self.db_session.add(new_user)
            await self.db_session.commit()
            await self.db_session.refresh(new_user)
            return OnboardingUserRead.model_validate(new_user)
        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in create_user: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error in create_user: {str(e)}")
            raise

    # --- READ ---
    async def get_user_by_id(self, user_id: int) -> Optional[OnboardingUserRead]:
        try:
            query = select(OnboardingUser).where(OnboardingUser.id == user_id)
            result = await self.db_session.execute(query)
            user = result.scalar_one_or_none()
            return OnboardingUserRead.model_validate(user) if user else None
        except SQLAlchemyError as e:
            logger.exception(f"Database error in get_user_by_id: {str(e)}")
            raise

    async def list_users(self, skip: int = 0, limit: int = 100) -> List[OnboardingUserRead]:
        try:
            query = select(OnboardingUser).offset(skip).limit(limit)
            result = await self.db_session.execute(query)
            users = result.scalars().all()
            return [OnboardingUserRead.model_validate(u) for u in users]
        except SQLAlchemyError as e:
            logger.exception(f"Database error in list_users: {str(e)}")
            raise

    # --- UPDATE ---
    async def update_user(self, user_id: int, update_data: OnboardingUserUpdate) -> OnboardingUserRead:
        try:
            query = select(OnboardingUser).where(OnboardingUser.id == user_id)
            result = await self.db_session.execute(query)
            user = result.scalar_one()

            # Dynamically update fields
            for field, value in update_data.model_dump(exclude_unset=True).items():
                if hasattr(user, field):
                    setattr(user, field, value)

            await self.db_session.commit()
            await self.db_session.refresh(user)
            return OnboardingUserRead.model_validate(user)
        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in update_user: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error in update_user: {str(e)}")
            raise

    # --- DELETE ---
    async def delete_user(self, user_id: int) -> None:
        try:
            query = select(OnboardingUser).where(OnboardingUser.id == user_id)
            result = await self.db_session.execute(query)
            user = result.scalar_one_or_none()
            if user:
                await self.db_session.delete(user)
                await self.db_session.commit()
        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in delete_user: {str(e)}")
            raise
