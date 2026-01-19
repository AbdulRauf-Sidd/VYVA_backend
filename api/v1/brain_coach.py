from sqlalchemy import select, func
from fastapi import APIRouter, Depends, HTTPException, status, Path, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List
from core.database import get_db
from schemas.brain_coach import BrainCoachQuestionRead, BrainCoachQuestionCreate, BrainCoachResponseRead, BrainCoachResponseCreate, BrainCoachStatsRead, DailySessionActivityResponse, SessionHistoryResponse, SessionHistoryItem
from repositories.brain_coach import BrainCoachQuestionRepository, BrainCoachQuestionCreate, BrainCoachResponseRepository, BrainCoachResponseCreate
import logging
from models.brain_coach import BrainCoachResponses
from models.user import User
import uuid
from repositories.user import UserRepository
from schemas.user import UserCreate, UserUpdate
from typing import Optional
# from services.whatsapp_service import whatsapp
from services.email_service import EmailService
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/questions", response_model=BrainCoachQuestionRead, status_code=status.HTTP_201_CREATED)
async def create_question_with_translations(
    question_data: BrainCoachQuestionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new question with translations"""
    try:
        # Validate input data
        if not question_data.translations:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one translation is required"
            )
        
        # Check for duplicate languages in the same request
        languages = [t.language for t in question_data.translations]
        if len(languages) != len(set(languages)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate languages found in translations"
            )
        
        # Validate language codes (basic validation)
        valid_languages = {"en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko"}
        for translation in question_data.translations:
            if translation.language not in valid_languages:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid language code: {translation.language}. Valid codes are: {sorted(valid_languages)}"
                )
        
        repo = BrainCoachQuestionRepository(db)
        created_question = await repo.create_question_with_translations(question_data)
        
        if not created_question:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create question"
            )
            
        return created_question

    except HTTPException:
        # Re-raise HTTP exceptions so they propagate correctly
        raise
        
    except ValueError as e:
        # Handle validation errors from repository
        logger.warning(f"Validation error creating question: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except IntegrityError as e:
        # Handle database integrity errors (duplicate keys, foreign key violations)
        logger.error(f"Database integrity error creating question: {str(e)}")
        await db.rollback()
        
        if "uq_question_language" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A translation for this language already exists for the question"
            )
        elif "foreign key" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid question reference"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Database integrity error occurred"
            )
            
    except SQLAlchemyError as e:
        # Handle other SQLAlchemy errors
        logger.error(f"Database error creating question: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while creating question"
        )
        
    except Exception as e:
        # Handle any other unexpected errors
        logger.exception(f"Unexpected error creating question: {str(e)}")
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating question"
        )

@router.get("/questions/{question_id}", response_model=BrainCoachQuestionRead)
async def get_question_by_id(
    question_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a complete question with all translations by ID"""
    try:
        # Validate question_id parameter
        if question_id <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question ID must be a positive integer"
            )
        
        repo = BrainCoachQuestionRepository(db)
        question = await repo.get_question_by_id(question_id)
        
        if not question:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Question with ID {question_id} not found"
            )
            
        return question

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except ValueError as e:
        # Handle validation errors
        logger.warning(f"Validation error retrieving question {question_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except SQLAlchemyError as e:
        # Handle database errors
        logger.error(f"Database error retrieving question {question_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while retrieving question"
        )
        
    except Exception as e:
        # Handle any other unexpected errors
        logger.exception(f"Unexpected error retrieving question {question_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while retrieving question"
        )

@router.get("/questions")
async def get_questions_by_filters(
    session: Optional[int] = None,
    tier: Optional[int] = None,
    question_type: Optional[str] = None,
    language: str = "en",
    db: AsyncSession = Depends(get_db)
):
    try:
        if session is not None and session <= 0:
            raise HTTPException(status_code=400, detail="Session must be a positive integer")
        if tier is not None and tier <= 0:
            raise HTTPException(status_code=400, detail="Tier must be a positive integer")
        if question_type is not None and not question_type.strip():
            raise HTTPException(status_code=400, detail="Question type cannot be empty")
        if not language.strip():
            raise HTTPException(status_code=400, detail="Language cannot be empty")

        repo = BrainCoachQuestionRepository(db)
        questions = await repo.get_questions_by_filters(
            session=session,
            tier=tier,
            question_type=question_type,
            language=language
        )

        if not questions:
            raise HTTPException(
                status_code=404,
                detail="No questions found for the given criteria"
            )

        session_id = str(uuid.uuid4()).replace("-", "")[:15]

        return {"session_id": session_id, "questions": questions}

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Unexpected error fetching brain coach questions: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching questions"
        )

from typing import Annotated



@router.post("/user-responses/{user_id}", response_model=BrainCoachResponseRead, status_code=status.HTTP_201_CREATED)
async def create_response(
    response_data: BrainCoachResponseCreate,
    user_id: int = Path(..., description="The ID of the user"),
    db: AsyncSession = Depends(get_db)
):
    """Create a new brain coach response"""
    try:
        logger.info(f"Creating response for user_id: {user_id} with data: {response_data}")
        repo = BrainCoachResponseRepository(db)
        # response_data.user_id = user_id  # Ensure the user_id from path is used
        new_response = BrainCoachResponses(
            session_id = response_data.session_id,
            user_id = user_id,
            question_id = response_data.question_id,
            # category = response_data.category,
            user_answer = response_data.user_answer,
            score = response_data.score
        )
        db.add(new_response)
        await db.commit()
        await db.refresh(new_response)
        return BrainCoachResponseRead.model_validate(new_response)

        created_response = await repo.create_response(response_data)
        return created_response

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.exception(f"Unexpected error creating response: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
        
@router.get("/brain-coach-info/{user_id}", response_model=BrainCoachStatsRead)
async def get_brain_coach_info(
    user_id: int = Path(..., description="The ID of the user"),
    days: int = Query(7, ge=1),
    db: AsyncSession = Depends(get_db)
):
    try:
        repo = BrainCoachResponseRepository(db)
        stats = await repo.get_brain_coach_info(user_id, days)
        return stats

    except Exception as e:
        logger.exception(f"Unexpected error retrieving brain coach info: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
        
@router.get("/cognitive-trend/{user_id}")
async def get_cognitive_trend(
    user_id: int = Path(..., description="The ID of the user"),
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db)
):
    repo = BrainCoachResponseRepository(db)
    rows = await repo.get_cognitive_trend(user_id, days)

    if not rows:
        return {
            "trend": [],
            "average": 0,
            "best_day": None,
            "improvement": 0
        }

    # format for recharts
    trend = [
        {
            "date": r.date.strftime("%b %d"),
            "score": round(float(r.avg_score), 2)
        }
        for r in rows
    ]

    scores = [float(r.avg_score) for r in rows]

    average = round(sum(scores) / len(scores), 2)

    best = max(rows, key=lambda r: r.avg_score)

    improvement = round(((scores[-1] - scores[0]) / scores[0]) * 100, 2)

    return {
        "trend": trend,
        "average": average,
        "best_day": best.date.strftime("%b %d"),
        "best_score": round(float(best.avg_score), 2),
        "improvement": improvement
    }
    
@router.get(
    "/daily-session-activity/{user_id}",
    response_model=DailySessionActivityResponse
)
async def daily_session_activity(
    user_id: int = Path(..., description="User ID"),
    days: int = Query(7, ge=1),
    db: AsyncSession = Depends(get_db)
):
    """Return daily session counts for a user over the past 'days' days"""
    try:
        repo = BrainCoachResponseRepository(db)
        trend = await repo.get_daily_session_activity(user_id, days)

        if not trend:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No session activity found for the user in the given time frame"
            )

        return {"trend": trend}

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error fetching daily session activity: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
        
@router.get("/session-history/{user_id}")
async def get_session_history(
    user_id: int = Path(..., description="The ID of the user"),
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(10, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    Return session history in the format expected by the frontend.
    """
    try:
        start_date = datetime.utcnow() - timedelta(days=days)

        # Get all responses for this user in the last `days`
        stmt = select(BrainCoachResponses).where(
            BrainCoachResponses.user_id == user_id,
            BrainCoachResponses.created >= start_date
        ).order_by(BrainCoachResponses.created.asc())

        result = await db.execute(stmt)
        responses = result.scalars().all()

        if not responses:
            return {"sessions": [], "total": 0}

        # Group responses by session_id
        sessions_dict = {}
        for r in responses:
            if r.session_id not in sessions_dict:
                sessions_dict[r.session_id] = {
                    "session_id": r.session_id,
                    "date": r.created.strftime("%b %d, %Y"),
                    "Questions": 0,
                    "score": 0,
                    "duration": "0 min",
                    "accuracy": "0%",
                    "mood": "neutral"  # default, can enhance later
                }

            sessions_dict[r.session_id]["Questions"] += 1
            sessions_dict[r.session_id]["score"] += r.score

        # Format sessions for frontend
        sessions = []
        for s in sessions_dict.values():
            total_questions = s["Questions"]
            s["score"] = round((s["score"] / total_questions) * 10 * 1, 2)  # convert to 0–100%
            s["accuracy"] = f"{round((s['score'] / 100) * 100)}%"  # simple placeholder
            s["duration"] = f"{total_questions * 1} min"  # 1 min per question, adjust as needed
            sessions.append(s)

        # Sort by date descending
        sessions.sort(key=lambda x: datetime.strptime(x["date"], "%b %d, %Y"), reverse=True)

        return {"sessions": sessions[offset:offset+limit], "total": len(sessions)}

    except Exception as e:
        logger.exception(f"Failed to fetch session history: {e}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )
        
        
# @router.get("/user-responses/{user_id}", response_model=List[BrainCoachResponseRead])
# async def get_user_responses(
#     user_id: int,
#     session_id: Optional[str] = None,
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get all responses for a user, optionally filtered by session_id"""
#     try:
#         repo = BrainCoachResponseRepository(db)
#         responses = await repo.get_responses_by_user_and_session(user_id, session_id)
        
#         if not responses:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail="No responses found for the given criteria"
#             )
            
#         return responses

#     except HTTPException:
#         raise
#     except Exception as e:
#         logger.exception(f"Unexpected error retrieving responses: {str(e)}")
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Internal server error"
#         )
    
email_service = EmailService()

# @router.put(
#     "/report/{user_id}", 
#     summary="Update user",
#     description="Update an existing user's information"
# )
# async def send_report(
#     user_id: int,
#     user_data: UserFeedback,
#     db: AsyncSession = Depends(get_db)
# ):
#     """
#     Update a user's information.
    
#     - **user_id**: The unique identifier of the user to update
#     - **user_data**: The updated user data (only provided fields will be updated)
#     """
#     repo = UserRepository(db)
#     try:
#         # Check if user exists first
#         # existing_user = await repo.get_user_by_id(user_id)
#         existing_user = await db.get(User, user_id)
#         if not existing_user:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=f"User with ID {user_id} not found"
#             )
        
#         # Check if email is being updated and if it's already taken
#         # if user_data.email: TODO remove this after event
#         #     user_with_email = await repo.get_user_by_email(user_data.email)
#         #     if user_with_email and user_with_email.id != user_id:
#         #         raise HTTPException(
#         #             status_code=status.HTTP_400_BAD_REQUEST,
#         #             detail="Email already in use by another user"
#         #         )
#         email = user_data.email
#         phone_number = user_data.phone_number
#         name = user_data.name if user_data.name else "N/A"
#         suggestions = user_data.suggestions if user_data.suggestions else "N/A"
#         performance_tier = user_data.performance_tier if user_data.performance_tier else "N/A"

#         if name.strip():
#             if len(name.strip().split(" ")) > 1:
#                 first_name, last_name = name.strip().split(" ", 1)
#             else:
#                 first_name = name.strip()
#                 last_name = ""
#         else:
#             first_name = "N/A"
#             last_name = "N/A"

#         logger.info(f"Parsed name: first_name='{first_name}', last_name='{last_name}'")

#         # user_data = UserUpdate(email=email, phone_number=phone_number, first_name=first_name, last_name=last_name)
        
#         # updated_user = await repo.update_user(user_id, user_data)
#         existing_user.email = email
#         existing_user.phone_number = phone_number
#         existing_user.first_name = first_name
#         existing_user.last_name = last_name
#         await db.commit()
#         await db.refresh(existing_user)
#         updated_user = existing_user
#         if not updated_user:
#             raise HTTPException(
#                 status_code=status.HTTP_404_NOT_FOUND,
#                 detail=f"User with ID {user_id} not found after update"
#             )
#         else:
#             logger.info(f"User {user_id} updated successfully with data: {user_data}")
#             brain_coach_response_repo = BrainCoachResponseRepository(db)
#             brain_coach_question_repo = BrainCoachQuestionRepository(db)
#             responses = await brain_coach_response_repo.get_responses_by_user_and_session(user_id)
#             logger.info(f"User {user_id} has {len(responses)} brain coach responses")
 
#             report_content = await construct_email_brain_coach_message(responses, brain_coach_question_repo)            

#             if email:
#                 await email_service.send_brain_coach_report(email, report_content, name, suggestions, performance_tier, language='es')
#             elif phone_number:
#                 whatsapp_content = await construct_whatsapp_brain_coach_message(first_name, report_content, suggestions)
#                 await whatsapp.send_brain_coach_report(phone_number, whatsapp_content)

#         return updated_user
#     except HTTPException:
#         raise
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to update user: {str(e)}"
#         )