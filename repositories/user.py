from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from typing import Optional, List
import logging
from sqlalchemy.orm import selectinload
from models.user import User
from schemas.user import UserCreate, UserUpdate, UserRead

logger = logging.getLogger(__name__)

class UserRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_user(self, user_data: UserCreate) -> UserRead:
        try:
            new_user = User(**user_data.model_dump())
            self.db_session.add(new_user)
            await self.db_session.commit()

            # Refresh the user with eager loading of relationships
            await self.db_session.refresh(new_user)

            # Now explicitly load the relationships to avoid greenlet error
            query = (
                select(User)
                .where(User.id == new_user.id)
                .options(
                    selectinload(User.long_term_conditions),
                    selectinload(User.topics_of_interest),
                    selectinload(User.preferred_activities)
                )
            )
            result = await self.db_session.execute(query)
            user_with_relations = result.scalar_one()

            return UserRead.model_validate(user_with_relations)

        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in create_user: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error in create_user: {str(e)}")
            raise

    async def get_user_by_id(self, user_id: int) -> Optional[UserRead]:
        try:
            query = (
                select(User)
                .where(User.id == user_id)
                .options(
                    selectinload(User.long_term_conditions),
                    selectinload(User.topics_of_interest),
                    selectinload(User.preferred_activities)
                )
            )
            result = await self.db_session.execute(query)
            user = result.scalar_one_or_none()

            if user:
                return UserRead.model_validate(user)
            return None
        except SQLAlchemyError as e:
            logger.exception(f"Database error in get_user_by_id: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in get_user_by_id: {str(e)}")
            raise

    async def get_user_by_email(self, email: str) -> Optional[UserRead]:
        try:
            query = (
                select(User)
                .where(User.email == email)
                .options(
                    selectinload(User.long_term_conditions),
                    selectinload(User.topics_of_interest),
                    selectinload(User.preferred_activities)
                )
            )
            result = await self.db_session.execute(query)
            user = result.scalar_one_or_none()

            if user:
                return UserRead.model_validate(user)
            return None
        except SQLAlchemyError as e:
            logger.exception(f"Database error in get_user_by_email: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in get_user_by_email: {str(e)}")
            raise

    async def get_all_users(self, skip: int = 0, limit: int = 100) -> List[UserRead]:
        try:
            query = (
                select(User)
                .offset(skip)
                .limit(limit)
                .options(
                    selectinload(User.long_term_conditions),
                    selectinload(User.topics_of_interest),
                    selectinload(User.preferred_activities)
                )
            )
            result = await self.db_session.execute(query)
            users = result.scalars().all()

            return [UserRead.model_validate(user) for user in users]
        except SQLAlchemyError as e:
            logger.exception(f"Database error in get_all_users: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error in get_all_users: {str(e)}")
            raise

    async def update_user(self, user_id: int, user_data: UserUpdate) -> Optional[UserRead]:
        try:
            # Get the update data, excluding unset values
            update_data = user_data.model_dump(exclude_unset=True)
            
            if not update_data:
                return await self.get_user_by_id(user_id)
            
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(**update_data)
                .execution_options(synchronize_session="fetch")
            )
            
            await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            # Return the updated user
            return await self.get_user_by_id(user_id)
        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in update_user: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error in update_user: {str(e)}")
            raise

    async def delete_user(self, user_id: int) -> bool:
        try:
            stmt = delete(User).where(User.id == user_id)
            result = await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            return result.rowcount > 0
        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in delete_user: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error in delete_user: {str(e)}")
            raise

    async def deactivate_user(self, user_id: int) -> Optional[UserRead]:
        try:
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(is_active=False)
                .execution_options(synchronize_session="fetch")
            )
            
            await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            return await self.get_user_by_id(user_id)
        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in deactivate_user: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error in deactivate_user: {str(e)}")
            raise

    async def activate_user(self, user_id: int) -> Optional[UserRead]:
        try:
            stmt = (
                update(User)
                .where(User.id == user_id)
                .values(is_active=True)
                .execution_options(synchronize_session="fetch")
            )
            
            await self.db_session.execute(stmt)
            await self.db_session.commit()
            
            return await self.get_user_by_id(user_id)
        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in activate_user: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error in activate_user: {str(e)}")
            raise