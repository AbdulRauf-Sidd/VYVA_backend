from fastapi import APIRouter, Depends, HTTPException, status, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from typing import List
from core.database import get_db
from schemas.brain_coach import BrainCoachQuestionRead, BrainCoachQuestionCreate, BrainCoachResponseRead, BrainCoachResponseCreate, UserFeedback
from repositories.brain_coach import BrainCoachQuestionRepository, BrainCoachResponseRepository
import logging
import uuid
from repositories.user import UserRepository
from schemas.user import UserCreate, UserUpdate
from typing import Optional
from services.whatsapp_service import whatsapp
import random
from services.helpers import construct_whatsapp_brain_coach_message, construct_email_brain_coach_message


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
    # user_id: str,
    session: Optional[int] = None,
    tier: Optional[int] = None,
    question_type: Optional[str] = None,
    language: str = "en",
    db: AsyncSession = Depends(get_db)
):
    """Get questions with filters and specific language"""
    try:
        # Validate query parameters
        if session is not None and session <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Session must be a positive integer if provided"
            )
        
        if tier is not None and tier <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tier must be a positive integer if provided"
            )
        
        if question_type is not None and not question_type.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Question type cannot be empty if provided"
            )
        
        if not language.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Language cannot be empty"
            )
        
       
        random_number = random.randint(1, 14)
        
        repo = BrainCoachQuestionRepository(db)
        questions = await repo.get_questions_by_filters(
            session=random_number,
            tier=tier,
            question_type=question_type,
            language=language
        )

        if not questions:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No questions found for the given criteria"
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

        
        return {"user_id": user.id, "questions": questions}
        
        # return questions

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
        
    except ValueError as e:
        # Handle validation errors
        logger.warning(f"Validation error filtering questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
        
    except SQLAlchemyError as e:
        # Handle database errors
        logger.error(f"Database error filtering questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error occurred while filtering questions"
        )
        
    except Exception as e:
        # Handle any other unexpected errors
        logger.exception(f"Unexpected error filtering questions: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while filtering questions"
        )

from typing import Annotated

@router.post("/user-responses/{user_id}", response_model=BrainCoachResponseRead, status_code=status.HTTP_201_CREATED)
async def create_response(
    user_id: int,
    response_data: BrainCoachResponseCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new brain coach response"""
    try:
        logger.info(f"Creating response for user_id: {user_id} with data: {response_data}")
        repo = BrainCoachResponseRepository(db)
        response_data.user_id = user_id  # Ensure the user_id from path is used
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

@router.get("/user-responses/{user_id}", response_model=List[BrainCoachResponseRead])
async def get_user_responses(
    user_id: int,
    session_id: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Get all responses for a user, optionally filtered by session_id"""
    try:
        repo = BrainCoachResponseRepository(db)
        responses = await repo.get_responses_by_user_and_session(user_id, session_id)
        
        if not responses:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No responses found for the given criteria"
            )
            
        return responses

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error retrieving responses: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error"
        )
    
from services.email_service import EmailService

email_service = EmailService()

@router.put(
    "/report/{user_id}", 
    summary="Update user",
    description="Update an existing user's information"
)
async def send_report(
    user_id: Annotated[int, Path(..., description="The ID of the user")],
    user_data: UserFeedback,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a user's information.
    
    - **user_id**: The unique identifier of the user to update
    - **user_data**: The updated user data (only provided fields will be updated)
    """
    repo = UserRepository(db)
    try:
        # Check if user exists first
        existing_user = await repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Check if email is being updated and if it's already taken
        # if user_data.email: TODO remove this after event
        #     user_with_email = await repo.get_user_by_email(user_data.email)
        #     if user_with_email and user_with_email.id != user_id:
        #         raise HTTPException(
        #             status_code=status.HTTP_400_BAD_REQUEST,
        #             detail="Email already in use by another user"
        #         )
        email = user_data.email
        phone_number = user_data.phone_number
        name = user_data.name if user_data.name else "N/A"
        suggestions = user_data.suggestions if user_data.suggestions else "N/A"
        performance_tier = user_data.performance_tier if user_data.performance_tier else "N/A"

        if name.strip():
            if len(name.strip().split(" ")) > 1:
                first_name, last_name = name.strip().split(" ", 1)
            else:
                first_name = name.strip()
                last_name = ""
        else:
            first_name = "N/A"
            last_name = "N/A"

        logger.info(f"Parsed name: first_name='{first_name}', last_name='{last_name}'")

        user_data = UserUpdate(email=email, phone_number=phone_number, first_name=first_name, last_name=last_name)
        
        updated_user = await repo.update_user(user_id, user_data)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found after update"
            )
        else:
            logger.info(f"User {user_id} updated successfully with data: {user_data}")
            brain_coach_response_repo = BrainCoachResponseRepository(db)
            brain_coach_question_repo = BrainCoachQuestionRepository(db)
            responses = await brain_coach_response_repo.get_responses_by_user_and_session(user_id)
            logger.info(f"User {user_id} has {len(responses)} brain coach responses")
 
            report_content = await construct_email_brain_coach_message(responses, brain_coach_question_repo)            

            if email:
                await email_service.send_brain_coach_report(email, report_content, name, suggestions, performance_tier, language='es')
            elif phone_number:
                whatsapp_content = construct_whatsapp_brain_coach_message(first_name, report_content, suggestions)
                await whatsapp.send_brain_coach_report(phone_number, whatsapp_content)

        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )