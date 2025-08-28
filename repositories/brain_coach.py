# repositories/brain_coach_questions.py
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import select
import logging
from fastapi_cache.decorator import cache
from core.database import get_db
from schemas.brain_coach import BrainCoachQuestionCreate, BrainCoachQuestionRead, BrainCoachResponseBase, BrainCoachResponseRead, BrainCoachResponseCreate
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses

logger = logging.getLogger(__name__)

class BrainCoachQuestionRepository:
    def __init__(self, db_session: get_db):
        self.db_session = db_session


    # @cache(expire=300)
    async def get_questions_by_tier_and_session(self, tier: int, session: int, limit: int = 7):
        print(0)
        try:
            if tier < 1 or session < 1:
                raise ValueError("Tier and session must be positive integers")
            if limit < 1 or limit > 100:
                raise ValueError("Limit must be between 1 and 100")

            print('1')

            query = (
                select(BrainCoachQuestions)
                .where(BrainCoachQuestions.tier == tier, BrainCoachQuestions.session == session)
                .limit(limit)
            )
            result = await self.db_session.execute(query)
            db_questions = result.scalars().all()

            if not db_questions:
                return []  # Return empty list instead of raising 404 (let endpoint decide)

            print('hi')
            return [BrainCoachQuestionRead.model_validate(q) for q in db_questions]

        except SQLAlchemyError as e:
            logger.exception(f"Database error fetching questions: {str(e)}")
            raise  # Re-raise for endpoint to handle
        except Exception as e:
            logger.exception(f"Unexpected repository error: {str(e)}")
            raise  # Re-raise for endpoint to handle

    # In your BrainCoachQuestionRepository class
    async def create_question(self, question_data: BrainCoachQuestionCreate) -> BrainCoachQuestionRead:
        try:
            new_question = BrainCoachQuestions(**question_data.model_dump())
            self.db_session.add(new_question)
            await self.db_session.commit()
            await self.db_session.refresh(new_question)
            return BrainCoachQuestionRead.model_validate(new_question)

        except SQLAlchemyError as e:
            await self.db_session.rollback()
            logger.exception(f"Database error in create_question: {str(e)}")
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.exception(f"Unexpected error in create_question: {str(e)}")
            raise


    async def get_random_question_by_tier_and_session(self, tier: int, session: int):
        try:
            if tier < 1 or session < 1:
                raise ValueError("Tier and session must be positive integers")

            query = (
                select(BrainCoachQuestions)
                .where(BrainCoachQuestions.tier == tier, BrainCoachQuestions.session == session)
                .order_by(func.random())
                .limit(1)
            )
            result = await self.db_session.execute(query)
            return BrainCoachQuestionRead.model_validate(result.scalar_one_or_none())

        except SQLAlchemyError as e:
            logger.exception(f"Database error fetching random question: {str(e)}")
            raise
        except Exception as e:
            logger.exception(f"Unexpected repository error: {str(e)}")
            raise



class BrainCoachResponseRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_response(
        self, response_data: BrainCoachResponseCreate
    ) -> BrainCoachResponseRead:
        """Create a new brain coach response"""
        new_response = BrainCoachResponses(**response_data.model_dump())
        self.db.add(new_response)
        await self.db.commit()
        await self.db.refresh(new_response)
        return BrainCoachResponseRead.model_validate(new_response)

    async def get_response_by_id(
        self, response_id: int
    ) -> Optional[BrainCoachResponseRead]:
        """Get a response by its ID"""
        query = select(BrainCoachResponses).where(BrainCoachResponses.id == response_id)
        result = await self.db.execute(query)
        response = result.scalar_one_or_none()

        if response:
            return BrainCoachResponseRead.model_validate(response)
        return None
