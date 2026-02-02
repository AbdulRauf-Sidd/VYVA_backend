"""
Symptom Checker Repository

Data access layer for symptom checker interactions.
"""

import logging
from typing import Optional, List
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from models.symptom_checker import SymptomCheckerResponse
from models.user import User, Caretaker
from schemas.symptom_checker import (
    SymptomCheckerInteractionCreate,
    SymptomCheckerInteractionRead
)

logger = logging.getLogger(__name__)


class SymptomCheckerRepository:
    """Repository for symptom checker interactions."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create_interaction(
        self, 
        interaction_data: SymptomCheckerInteractionCreate
    ) -> SymptomCheckerInteractionRead:
        """Create a new symptom checker interaction."""
        try:
            # Check if interaction already exists by conversation_id
            existing = await self.db_session.execute(
                select(SymptomCheckerResponse).where(
                    SymptomCheckerResponse.conversation_id == interaction_data.conversation_id
                )
            )
            existing_record = existing.scalar_one_or_none()
            
            if existing_record:
                # Update existing record
                for field, value in interaction_data.model_dump(exclude_unset=True).items():
                    if value is not None:
                        setattr(existing_record, field, value)
                
                await self.db_session.commit()
                await self.db_session.refresh(existing_record)
                logger.info(f"Updated symptom checker interaction ID {existing_record.id}")
                return SymptomCheckerInteractionRead.model_validate(existing_record)
            else:
                # Create new record
                # Note: symptoms field is required, so we need to provide a default
                interaction_dict = interaction_data.model_dump()
                if "symptoms" not in interaction_dict or not interaction_dict.get("symptoms"):
                    interaction_dict["symptoms"] = "Symptom checker call completed"
                
                new_interaction = SymptomCheckerResponse(**interaction_dict)
                self.db_session.add(new_interaction)
                await self.db_session.commit()
                await self.db_session.refresh(new_interaction)
                logger.info(f"Created symptom checker interaction ID {new_interaction.id}")
                return SymptomCheckerInteractionRead.model_validate(new_interaction)
                
        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error creating interaction: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error creating interaction: {str(e)}")
            raise

    async def get_by_id(self, interaction_id: int) -> Optional[SymptomCheckerInteractionRead]:
        """Get a single interaction by ID."""
        try:
            result = await self.db_session.execute(
                select(SymptomCheckerResponse).where(
                    SymptomCheckerResponse.id == interaction_id
                )
            )
            interaction = result.scalar_one_or_none()
            
            if interaction:
                return SymptomCheckerInteractionRead.model_validate(interaction)
            return None
            
        except SQLAlchemyError as e:
            logger.exception(f"Database error getting interaction by ID: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting interaction by ID: {str(e)}")
            raise

    async def get_by_conversation_id(
        self, 
        conversation_id: str
    ) -> Optional[SymptomCheckerInteractionRead]:
        """Get interaction by conversation_id."""
        try:
            result = await self.db_session.execute(
                select(SymptomCheckerResponse).where(
                    SymptomCheckerResponse.conversation_id == conversation_id
                )
            )
            interaction = result.scalar_one_or_none()
            
            if interaction:
                return SymptomCheckerInteractionRead.model_validate(interaction)
            return None
            
        except SQLAlchemyError as e:
            logger.exception(f"Database error getting interaction by conversation_id: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting interaction by conversation_id: {str(e)}")
            raise

    async def get_by_user_id(
        self, 
        user_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> List[SymptomCheckerInteractionRead]:
        """Get all interactions for a specific user."""
        try:
            order_timestamp = func.coalesce(
                SymptomCheckerResponse.call_timestamp,
                SymptomCheckerResponse.created_at
            )
            query = (
                select(SymptomCheckerResponse)
                .where(SymptomCheckerResponse.user_id == user_id)
                .order_by(order_timestamp.desc())
                .order_by(SymptomCheckerResponse.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            
            result = await self.db_session.execute(query)
            interactions = result.scalars().all()
            
            return [
                SymptomCheckerInteractionRead.model_validate(interaction)
                for interaction in interactions
            ]
            
        except SQLAlchemyError as e:
            logger.exception(f"Database error getting interactions by user_id: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting interactions by user_id: {str(e)}")
            raise

    async def get_by_caretaker(
        self,
        caretaker_id: int,
        skip: int = 0,
        limit: int = 100,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SymptomCheckerInteractionRead]:
        """Get all interactions for users assigned to a caretaker."""
        try:
            order_timestamp = func.coalesce(
                SymptomCheckerResponse.call_timestamp,
                SymptomCheckerResponse.created_at
            )
            # Build query with joins
            query = (
                select(SymptomCheckerResponse)
                .join(User, SymptomCheckerResponse.user_id == User.id)
                .where(User.caretaker_id == caretaker_id)
            )
            
            # Apply optional filters
            if user_id:
                query = query.where(SymptomCheckerResponse.user_id == user_id)
            
            if start_date:
                query = query.where(
                    or_(
                        SymptomCheckerResponse.call_timestamp >= start_date,
                        SymptomCheckerResponse.created_at >= start_date
                    )
                )
            
            if end_date:
                query = query.where(
                    or_(
                        SymptomCheckerResponse.call_timestamp <= end_date,
                        SymptomCheckerResponse.created_at <= end_date
                    )
                )
            
            # Order and paginate
            query = (
                query
                .order_by(order_timestamp.desc())
                .order_by(SymptomCheckerResponse.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            
            result = await self.db_session.execute(query)
            interactions = result.scalars().all()
            
            return [
                SymptomCheckerInteractionRead.model_validate(interaction)
                for interaction in interactions
            ]
            
        except SQLAlchemyError as e:
            logger.exception(f"Database error getting interactions by caretaker: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting interactions by caretaker: {str(e)}")
            raise

    async def get_recent_interactions(
        self,
        limit: int = 10,
        user_id: Optional[int] = None
    ) -> List[SymptomCheckerInteractionRead]:
        """Get recent interactions, optionally filtered by user."""
        try:
            order_timestamp = func.coalesce(
                SymptomCheckerResponse.call_timestamp,
                SymptomCheckerResponse.created_at
            )
            query = select(SymptomCheckerResponse)
            
            if user_id:
                query = query.where(SymptomCheckerResponse.user_id == user_id)
            
            query = (
                query
                .order_by(order_timestamp.desc())
                .order_by(SymptomCheckerResponse.created_at.desc())
                .limit(limit)
            )
            
            result = await self.db_session.execute(query)
            interactions = result.scalars().all()
            
            return [
                SymptomCheckerInteractionRead.model_validate(interaction)
                for interaction in interactions
            ]
            
        except SQLAlchemyError as e:
            logger.exception(f"Database error getting recent interactions: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting recent interactions: {str(e)}")
            raise

    async def get_interactions_by_date_range(
        self,
        start_date: datetime,
        end_date: datetime,
        user_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[SymptomCheckerInteractionRead]:
        """Get interactions within a date range."""
        try:
            order_timestamp = func.coalesce(
                SymptomCheckerResponse.call_timestamp,
                SymptomCheckerResponse.created_at
            )
            query = select(SymptomCheckerResponse).where(
                or_(
                    and_(
                        SymptomCheckerResponse.call_timestamp >= start_date,
                        SymptomCheckerResponse.call_timestamp <= end_date
                    ),
                    and_(
                        SymptomCheckerResponse.call_timestamp.is_(None),
                        SymptomCheckerResponse.created_at >= start_date,
                        SymptomCheckerResponse.created_at <= end_date
                    )
                )
            )
            
            if user_id:
                query = query.where(SymptomCheckerResponse.user_id == user_id)
            
            query = (
                query
                .order_by(order_timestamp.desc())
                .order_by(SymptomCheckerResponse.created_at.desc())
                .offset(skip)
                .limit(limit)
            )
            
            result = await self.db_session.execute(query)
            interactions = result.scalars().all()
            
            return [
                SymptomCheckerInteractionRead.model_validate(interaction)
                for interaction in interactions
            ]
            
        except SQLAlchemyError as e:
            logger.exception(f"Database error getting interactions by date range: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error getting interactions by date range: {str(e)}")
            raise

    async def count_by_user_id(self, user_id: int) -> int:
        """Count total interactions for a user."""
        try:
            result = await self.db_session.execute(
                select(func.count(SymptomCheckerResponse.id)).where(
                    SymptomCheckerResponse.user_id == user_id
                )
            )
            return result.scalar_one() or 0
            
        except SQLAlchemyError as e:
            logger.exception(f"Database error counting interactions: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error counting interactions: {str(e)}")
            raise

    async def count_by_caretaker(
        self,
        caretaker_id: int,
        user_id: Optional[int] = None
    ) -> int:
        """Count total interactions for users assigned to a caretaker."""
        try:
            query = (
                select(func.count(SymptomCheckerResponse.id))
                .join(User, SymptomCheckerResponse.user_id == User.id)
                .where(User.caretaker_id == caretaker_id)
            )
            
            if user_id:
                query = query.where(SymptomCheckerResponse.user_id == user_id)
            
            result = await self.db_session.execute(query)
            return result.scalar_one() or 0
            
        except SQLAlchemyError as e:
            logger.exception(f"Database error counting interactions by caretaker: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error counting interactions by caretaker: {str(e)}")
            raise

