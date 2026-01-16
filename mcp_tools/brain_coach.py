from .mcp_instance import mcp
from datetime import time
from pydantic import BaseModel
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses, QuestionTranslations
from models.user import User
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from core.database import get_async_session
from enum import Enum
import uuid
from sqlalchemy import false
from services.helpers import construct_whatsapp_brain_coach_message
from services.whatsapp_service import whatsapp_service
from services.email_service import email_service

class QuestionType(str, Enum):
    TRIVIA = "trivia"
    COGNITIVE_ASSESSMENT = "cognitive_assessment"

class Language(str, Enum):
    ENGLISH = 'english'
    SPANISH = 'spanish'
    GERMAN = 'german'

class RetrieveQuestionsInput(BaseModel):
    user_id: int
    questions_type: QuestionType
    language: Language

class RetrieveQuestionsOutput(BaseModel):
    session_id: str
    questions: list[dict]
    
@mcp.tool(
    name="retrieve_questions",
    description=(
        "You will use this tool to retrieve the questions for a brain coach session."
        "You will call this tool when You're about to start the brain coach session."
        'You will pass the language the user is speaking in full form. if the user is speaking in english, you will pass english (all lower case)'
    )
)
async def retrieve_questions(input: RetrieveQuestionsInput) -> RetrieveQuestionsOutput:
    async with get_async_session() as db:

        answered_stmt = (
            select(BrainCoachResponses.question_id)
            .where(BrainCoachResponses.user_id == input.user_id)
        )
        answered_result = await db.execute(answered_stmt)
        answered_question_ids = [row[0] for row in answered_result.all()]

        language = (
            Language.SPANISH.value
            if input.questions_type == QuestionType.TRIVIA
            else input.language.value
        )

        stmt = (
            select(
                BrainCoachQuestions.id,
                BrainCoachQuestions.max_score,
                QuestionTranslations.question_text,
                QuestionTranslations.expected_answer,
                QuestionTranslations.scoring_logic,
                QuestionTranslations.question_type,
                QuestionTranslations.theme,
                QuestionTranslations.language,
            )
            .join(
                QuestionTranslations,
                QuestionTranslations.question_id == BrainCoachQuestions.id
            )
            .where(
                BrainCoachQuestions.category == input.questions_type.value,
                QuestionTranslations.language == language,
                BrainCoachQuestions.id.not_in(answered_question_ids)
                if answered_question_ids else True
            )
            .order_by(BrainCoachQuestions.id)
            .limit(6)
        )

        result = await db.execute(stmt)
        rows = result.all()

        questions = [
            {
                "id": row.id,
                "max_score": row.max_score,
                "question_text": row.question_text,
                "expected_answer": row.expected_answer,
                "scoring_logic": row.scoring_logic,
                "question_type": row.question_type,
                "theme": row.theme,
            }
            for row in rows
        ]

        session_id = str(uuid.uuid4())

        return {
            "session_id": session_id,
            "questions": questions
        }


class StoreAnswerInput(BaseModel):
    session_id: str
    user_id: int
    question_id: int
    score: int


@mcp.tool(
    name="store_user_answer",
    description=(
        "Store a user's response to a brain coach question."
        "You will call the tool every time the user answer's the questions."
    )
)
async def store_user_answer(input: StoreAnswerInput) -> dict:
    try:
        async with get_async_session() as db:
            response = BrainCoachResponses(
                session_id=input.session_id,
                user_id=input.user_id,
                question_id=input.question_id,
                score=input.score,
            )

            db.add(response)
            await db.commit()
            await db.refresh(response)

            return {
                "success": True,
            }
    except Exception as e:
        return {
            "success": False
        }

        
class SendBrainCoachReportInput(BaseModel):
    user_id: int
    session_id: str 
    question_type: QuestionType
    
@mcp.tool(
    name="send_brain_coach_report",
    description=(
        "You will use this tool to update an existing medication for a user."
        "You will call this when the user wants to update their medication details."
        "Times should be in 24-hour format."
    )
)
async def send_brain_coach_report(
    input: SendBrainCoachReportInput
) -> dict:
    async with get_async_session() as db:
        
        result = await db.execute(
            select(User).where(User.id == input.user_id)
        )
        user = result.scalar_one_or_none()

        if not user:
            return {
                "success": False,
                "message": "user not found"
            }
        
        query = (
            select(BrainCoachResponses)
            .where(
                BrainCoachResponses.user_id == user.id,
                BrainCoachResponses.session_id == input.session_id
            )
            .order_by(BrainCoachResponses.created.desc())
        )

        result = await db.execute(query)
        responses = result.scalars().all()
        report_content = []
        question_ids = []
        for response in responses:
            question_ids.append(response.question_id)

        language = (
            'spanish' if input.question_type == QuestionType.TRIVIA else user.preferred_consultation_language
        )

        query = (
            select(BrainCoachQuestions, QuestionTranslations)
            .join(
                QuestionTranslations,
                BrainCoachQuestions.id == QuestionTranslations.question_id
            )
            .where(
                BrainCoachQuestions.id.in_(question_ids) if question_ids else false(),
                QuestionTranslations.language == language
            )
            .order_by(BrainCoachQuestions.id)
        )

        result = await db.execute(query)
        questions = result.all()
        for question in questions:
            report_content.append({
                "question_text": question.question_text,
                "question_type": question.question_type,
                "theme": question.theme,
                'score': response.score,
                "max_score": question.max_score,
                'tier': question.tier,
                'session': question.session,
            })
        
        preferred_report_channel = user.preferred_reports_channel
        if preferred_report_channel == 'whatsapp':
            phone_number = None
            if user.is_primary_landline:
                phone_number = user.secondary_phone
            else:
                phone_number = user.phone_number

            if phone_number:
                whatsapp_content = await construct_whatsapp_brain_coach_message(user.first_name, report_content, "Well Done")
                await whatsapp_service.send_brain_coach_report(phone_number, whatsapp_content)
            else:
                if not user.email:
                    return {
                        "success": False,
                        "message": "email required"
                    }
                await email_service.send_brain_coach_report(user.email, report_content, user.full_name, "well Done", "1", language=user.preferred_consultation_language)
        else:
            if not user.email:
                return {
                    "success": False,
                    "message": "email required"
                }
            await email_service.send_brain_coach_report(user.email, report_content, user.full_name, "well Done", "1", language=user.preferred_consultation_language)