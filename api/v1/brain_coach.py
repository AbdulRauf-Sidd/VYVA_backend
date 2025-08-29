from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from core.database import get_db
from schemas.brain_coach import BrainCoachQuestionRead, BrainCoachQuestionCreate
from repositories.brain_coach import BrainCoachQuestionRepository
import logging
import uuid
from repositories.user import UserRepository
from schemas.user import UserCreate

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/get-questions", status_code=status.HTTP_200_OK)
async def get_questions_by_tier_and_session(
    user_id: str,
    tier: int,
    limit: int = 7,
    db: AsyncSession = Depends(get_db)
):
    try:

        #FUTURE UPDATE FOR DYNAMIC SESSION VALIDATION

        print(type(tier))


        repo = BrainCoachQuestionRepository(db)
        questions = await repo.get_questions_by_tier_and_session(int(tier), 1, limit)

        if not questions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No questions found for tier {tier}"
            )

        random_string = str(uuid.uuid4()).replace("-", "")[:15]

        empty_user_data = UserCreate(
            email=None,  # Email can be set later
            first_name=None,
            last_name=None,
            # All other fields will use their default None values
        )
        
        repo = UserRepository(db)
        user = await repo.create_user(empty_user_data)

        
        return {"session_id": random_string, user_id: user, "questions": questions}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.post("/create-question", response_model=BrainCoachQuestionRead, status_code=status.HTTP_201_CREATED)
async def create_question(
    question_data: BrainCoachQuestionCreate,
    db: AsyncSession = Depends(get_db)
):
    try:
        repo = BrainCoachQuestionRepository(db)
        created_question = await repo.create_question(question_data)
        return created_question

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.exception(f"Unexpected error creating question: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )

@router.get("/get-random-question", response_model=BrainCoachQuestionRead)
async def get_random_question_by_tier_and_session(
    tier: int,
    session: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        repo = BrainCoachQuestionRepository(db)
        question = await repo.get_random_question_by_tier_and_session(tier, session)

        if question is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No question found for tier {tier} and session {session}"
            )

        return question

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.exception(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
