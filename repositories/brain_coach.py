import logging
from sqlalchemy import select, and_
from typing import Optional, List
from core.database import get_db
from schemas.brain_coach import  BrainCoachResponseRead, BrainCoachResponseCreate, BrainCoachQuestionCreate, BrainCoachQuestionRead, BrainCoachQuestionReadWithLanguage, QuestionTranslationBase, QuestionTranslationRead
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses, BrainCoachQuestions, QuestionTranslations

logger = logging.getLogger(__name__)


class BrainCoachQuestionRepository:
    def __init__(self, db_session: get_db):
        self.db_session = db_session

    async def create_question_with_translations(
        self, question_data: BrainCoachQuestionCreate
    ) -> BrainCoachQuestionRead:
        """Create a new question with translations"""
        try:
            # Validate session and tier values
            if question_data.session <= 0:
                raise ValueError("Session must be a positive integer")
            if question_data.tier <= 0:
                raise ValueError("Tier must be a positive integer")
            if question_data.max_score and question_data.max_score < 0:
                raise ValueError("Max score must be a positive integer")

            # Validate translation data
            for translation in question_data.translations:
                if not translation.question_text.strip():
                    raise ValueError("Question text cannot be empty")
                if not translation.expected_answer.strip():
                    raise ValueError("Expected answer cannot be empty")
                if not translation.question_type.strip():
                    raise ValueError("Question type cannot be empty")
                if len(translation.language) > 20:
                    raise ValueError("Language code too long")
                if translation.theme and len(translation.theme) > 100:
                    raise ValueError("Theme too long")
                if translation.question_type and len(translation.question_type) > 100:
                    raise ValueError("Question type too long")

            # Create base question
            base_question = BrainCoachQuestions(
                session=question_data.session,
                tier=question_data.tier,
                max_score=question_data.max_score
            )
            self.db_session.add(base_question)
            await self.db_session.flush()

            # Create translations
            for translation in question_data.translations:
                new_translation = QuestionTranslations(
                    question_id=base_question.id,
                    language=translation.language,
                    question_text=translation.question_text,
                    expected_answer=translation.expected_answer,
                    scoring_logic=translation.scoring_logic,
                    question_type=translation.question_type,
                    theme=translation.theme
                )
                self.db_session.add(new_translation)

            await self.db_session.commit()
            await self.db_session.refresh(base_question)

            # Return the complete question with translations
            return await self.get_question_by_id(base_question.id)

        except Exception:
            await self.db_session.rollback()
            raise

    async def get_question_by_id(self, question_id: int) -> Optional[BrainCoachQuestionRead]:
        """Get a complete question with all translations by ID"""
        try:
            # Validate input
            if not isinstance(question_id, int) or question_id <= 0:
                raise ValueError("Question ID must be a positive integer")

            # Get base question
            query = select(BrainCoachQuestions).where(BrainCoachQuestions.id == question_id)
            result = await self.db_session.execute(query)
            question = result.scalar_one_or_none()

            if not question:
                logger.info(f"Question with ID {question_id} not found")
                return None

            # Get translations
            trans_query = select(QuestionTranslations).where(
                QuestionTranslations.question_id == question_id
            ).order_by(QuestionTranslations.language.asc())

            trans_result = await self.db_session.execute(trans_query)
            translations = trans_result.scalars().all()

            if not translations:
                logger.warning(f"Question {question_id} found but has no translations")
                return None

            # Convert translations to schema objects
            translation_schemas = []
            for translation in translations:
                try:
                    translation_schema = QuestionTranslationRead.model_validate(translation)
                    translation_schemas.append(translation_schema)
                except Exception as e:
                    logger.error(f"Failed to validate translation {translation.id} for question {question_id}: {str(e)}")
                    # Continue with other translations instead of failing completely
                    continue
                
            # Convert to schema
            question_data = BrainCoachQuestionRead(
                id=question.id,
                session=question.session,
                tier=question.tier,
                max_score=question.max_score,
                translations=translation_schemas
            )

            logger.debug(f"Successfully retrieved question {question_id} with {len(translation_schemas)} translations")
            return question_data

        except ValueError as e:
            logger.warning(f"Validation error retrieving question {question_id}: {str(e)}")
            raise ValueError(str(e))

        except Exception as e:
            logger.exception(f"Unexpected error retrieving question {question_id}: {str(e)}")
            raise Exception(f"Unexpected error occurred while retrieving question: {str(e)}")

    async def get_questions_by_filters(
        self,
        session: Optional[int] = None,
        tier: Optional[int] = None,
        question_type: Optional[str] = None,
        language: str = "en"
    ) -> List[BrainCoachQuestionReadWithLanguage]:
        """Get questions with filters and specific language"""
        try:
            # Validate input parameters
            if session is not None and (not isinstance(session, int) or session <= 0):
                raise ValueError("Session must be a positive integer if provided")

            if tier is not None and (not isinstance(tier, int) or tier <= 0):
                raise ValueError("Tier must be a positive integer if provided")

            if question_type is not None and not isinstance(question_type, str):
                raise ValueError("Question type must be a string if provided")

            if not isinstance(language, str) or not language.strip():
                raise ValueError("Language must be a non-empty string")

            if len(language) > 20:
                raise ValueError("Language code too long")

            # Validate language against known codes (optional but recommended)
            valid_languages = {"en", "es", "fr", "de", "it", "pt", "ru", "zh", "ja", "ko"}
            if language not in valid_languages:
                logger.warning(f"Uncommon language code requested: {language}")

            # Build query
            query = (
                select(BrainCoachQuestions, QuestionTranslations)
                .join(QuestionTranslations, BrainCoachQuestions.id == QuestionTranslations.question_id)
                .where(QuestionTranslations.language == language)
            )

            if session is not None:
                query = query.where(BrainCoachQuestions.session == session)

            if tier is not None:
                query = query.where(BrainCoachQuestions.tier == tier)

            if question_type is not None:
                if not question_type.strip():
                    raise ValueError("Question type cannot be empty if provided")
                query = query.where(QuestionTranslations.question_type == question_type)

            query = query.order_by(BrainCoachQuestions.id)

            # Execute query
            result = await self.db_session.execute(query)
            results = result.all()

            if not results:
                logger.info(f"No questions found for filters: session={session}, tier={tier}, question_type={question_type}, language={language}")
                return []

            # Process results
            questions = []
            for question, translation in results:
                try:
                    question_data = BrainCoachQuestionReadWithLanguage(
                        id=question.id,
                        session=question.session,
                        tier=question.tier,
                        max_score=question.max_score,
                        question_text=translation.question_text,
                        expected_answer=translation.expected_answer,
                        scoring_logic=translation.scoring_logic,
                        question_type=translation.question_type,
                        theme=translation.theme,
                        language=translation.language
                    )
                    questions.append(question_data)
                except Exception as e:
                    logger.error(f"Failed to process question {question.id} with translation {translation.id}: {str(e)}")
                    # Continue processing other questions instead of failing completely
                    continue
                
            logger.debug(f"Found {len(questions)} questions for filters: session={session}, tier={tier}, question_type={question_type}, language={language}")
            return questions

        except ValueError as e:
            logger.warning(f"Validation error in get_questions_by_filters: {str(e)}")
            raise ValueError(str(e))


        except Exception as e:
            logger.exception(f"Unexpected error in get_questions_by_filters: {str(e)}")
            raise Exception(f"Unexpected error occurred while filtering questions: {str(e)}")

            
    async def get_question_translation(
        self, question_id: int, language: str = "en"
    ) -> Optional[BrainCoachQuestionReadWithLanguage]:
        """Get a specific question in a specific language"""
        query = (
            select(BrainCoachQuestions, QuestionTranslations)
            .join(QuestionTranslations, BrainCoachQuestions.id == QuestionTranslations.question_id)
            .where(
                BrainCoachQuestions.id == question_id,
                QuestionTranslations.language == language
            )
        )
        
        result = await self.db_session.execute(query)
        row = result.first()
        
        if not row:
            return None
        
        question, translation = row
        return BrainCoachQuestionReadWithLanguage(
            id=question.id,
            session=question.session,
            tier=question.tier,
            max_score=question.max_score,
            question_text=translation.question_text,
            expected_answer=translation.expected_answer,
            scoring_logic=translation.scoring_logic,
            question_type=translation.question_type,
            theme=translation.theme,
            language=translation.language
        )

    async def add_translation_to_question(
        self, question_id: int, translation_data: QuestionTranslationBase
    ) -> QuestionTranslationRead:
        """Add a new translation to an existing question"""
        # Check if translation already exists
        existing_query = select(QuestionTranslations).where(
            and_(
                QuestionTranslations.question_id == question_id,
                QuestionTranslations.language == translation_data.language
            )
        )
        existing_result = await self.db_session.execute(existing_query)
        if existing_result.scalar_one_or_none():
            raise ValueError(f"Translation for language '{translation_data.language}' already exists for this question")
        
        # Check if question exists
        question_query = select(BrainCoachQuestions).where(BrainCoachQuestions.id == question_id)
        question_result = await self.db_session.execute(question_query)
        if not question_result.scalar_one_or_none():
            raise ValueError(f"Question with ID {question_id} not found")
        
        # Create new translation
        new_translation = QuestionTranslations(
            question_id=question_id,
            language=translation_data.language,
            question_text=translation_data.question_text,
            expected_answer=translation_data.expected_answer,
            scoring_logic=translation_data.scoring_logic,
            question_type=translation_data.question_type,
            theme=translation_data.theme
        )
        
        self.db_session.add(new_translation)
        await self.db_session.commit()
        await self.db_session.refresh(new_translation)
        
        return QuestionTranslationRead.model_validate(new_translation)



class BrainCoachResponseRepository:
    def __init__(self, db_session: get_db):
        self.db_session = db_session

    async def create_response(
        self, response_data: BrainCoachResponseCreate
    ) -> BrainCoachResponseRead:
        """Create a new brain coach response"""
        new_response = BrainCoachResponses(**response_data.model_dump())
        self.db_session.add(new_response)
        await self.db_session.commit()
        await self.db_session.refresh(new_response)
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

    async def get_responses_by_user_and_session(
        self, 
        user_id: int, 
        session_id: Optional[str] = None
    ) -> List[BrainCoachResponseRead]:
        """Get all responses for a user, optionally filtered by session_id"""
        query = select(BrainCoachResponses).where(BrainCoachResponses.user_id == user_id)
        
        if session_id:
            query = query.where(BrainCoachResponses.session_id == session_id)
        
        query = query.order_by(BrainCoachResponses.created.desc())
        
        result = await self.db_session.execute(query)
        responses = result.scalars().all()
        
        return [BrainCoachResponseRead.model_validate(response) for response in responses]