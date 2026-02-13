from models.organization import TemplateTypeEnum, TwilioWhatsappTemplates
from .mcp_instance import mcp
from datetime import time
from pydantic import BaseModel
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses, QuestionTranslations
from models.user import User
from sqlalchemy.orm import selectinload
from sqlalchemy import select, func
from core.database import get_async_session
from enum import Enum
import uuid
from sqlalchemy import false
from services.helpers import construct_whatsapp_brain_coach_message
from services.whatsapp_service import whatsapp_service
from services.email_service import email_service
from scripts.utils import LANGUAGE_MAP
import logging


logger = logging.getLogger(__name__)

class QuestionType(str, Enum):
    trivia = "trivia"
    cognitive_assessment = "cognitive_assessment"

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
        "the question type will always be enum. if the user wants cognitive excersices then question_type will be cognitive_assessment."
        "if the user wants trivia then question_type will be trivia"
    )
)
async def retrieve_questions(input: RetrieveQuestionsInput) -> RetrieveQuestionsOutput:
    async with get_async_session() as db:

        stmt = (
            select(func.count(func.distinct(BrainCoachResponses.session_id)))
            .where(BrainCoachResponses.user_id == input.user_id)
        )

        result = await db.execute(stmt)
        session_count = result.scalar_one()

        if input.questions_type.value == QuestionType.COGNITIVE_ASSESSMENT.value:
            target_session = session_count + 1
        else:
            target_session = 1

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
                QuestionTranslations.language == 'es',
                BrainCoachQuestions.session == target_session,
                # BrainCoachQuestions.id.not_in(answered_question_ids)
                # if answered_question_ids else True
            )
            .order_by(BrainCoachQuestions.id)
            .limit(6)
        )

        result = await db.execute(stmt)
        rows = result.all()

        memory_row = None
        other_rows = []
        
        for row in rows:
            if row.question_type in ("Memory", "Memoria"):
                memory_row = row
            else:
                other_rows.append(row)
        
        # rebuild ordered list
        ordered_rows = ([memory_row] if memory_row else []) + other_rows
        
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
            for row in ordered_rows
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
    user_answer: str


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
                user_answer=input.user_answer
            )

            db.add(response)
            await db.commit()
            await db.refresh(response)

            return {
                "success": True,
            }
    except Exception as e:
        logger.error(f"Error storing user answer: {e}")
        return {
            "success": False
        }

        
class SendBrainCoachReportInput(BaseModel):
    user_id: int
    session_id: str 
    question_type: QuestionType
    agent_notes_and_suggestions: str
    
@mcp.tool(
    name="send_brain_coach_report",
    description=(
        "You will use this tool to send the current sessions report to a user."
        "You will call this when the user wants to receive their brain coach report."
        "You will always send agent notes and suggestions in the report."
        "the agent notes and suggestions will be based on how the user did this session. " \
        "Examples for agent notes and suggestions: 'Good progress today. Continue memory recall exercises and repeat attention drills tomorrow.'"
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
            'spanish' if input.question_type == QuestionType.trivia.value else user.preferred_consultation_language
        )

        iso_language = LANGUAGE_MAP.get(language.lower() if language else "english")

        query = (
            select(BrainCoachQuestions, QuestionTranslations)
            .join(
                QuestionTranslations,
                BrainCoachQuestions.id == QuestionTranslations.question_id
            )
            .where(
                BrainCoachQuestions.id.in_(question_ids) if question_ids else false(),
                QuestionTranslations.language == iso_language
            )
            .order_by(BrainCoachQuestions.id)
        )

        result = await db.execute(query)
        questions = result.all()
        for question, translation in questions:
            score = 0
            for response in responses:
                if question.id == response.question_id:
                    score = response.score
                    break
                
            report_content.append({
                "question_text": translation.question_text,
                "question_type": translation.question_type,
                "theme": translation.theme,
                'score': score,
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
                stmt = (
                    select(TwilioWhatsappTemplates)
                    .where(
                        TwilioWhatsappTemplates.template_type == TemplateTypeEnum.brain_coach.value,
                        TwilioWhatsappTemplates.language == user.preferred_consultation_language,
                    )
                )
                
                result = await db.execute(stmt)
                template = result.scalars().first()
                whatsapp_template_id = template.template_id if template else None
                if not whatsapp_template_id:
                    logger.warning(f"No WhatsApp template found for language {user.preferred_consultation_language}")
                    return {
                        "success": False
                    }
                    
                whatsapp_content = construct_whatsapp_brain_coach_message(user.first_name, report_content, input.agent_notes_and_suggestions)
                print(question_ids, report_content, questions, responses, input.session_id)
                print(f"Constructed WhatsApp content: {whatsapp_content}, template_id: {whatsapp_template_id}")
                await whatsapp_service.send_message(phone_number, whatsapp_content, template_id=whatsapp_template_id)
                return {
                    "success": True,
                    "message": "Report sent via WhatsApp"
                }
            else:
                if not user.email:
                    return {
                        "success": False,
                        "message": "email required"
                    }
                await email_service.send_brain_coach_report(user.email, report_content, user.full_name, input.agent_notes_and_suggestions, "1", language=user.preferred_consultation_language)
                return {
                    "success": True,
                    "message": "Report sent via Email"
                }
        else:
            if not user.email:
                return {
                    "success": False,
                    "message": "email required"
                }
            await email_service.send_brain_coach_report(user.email, report_content, user.full_name, input.agent_notes_and_suggestions, "1", language=user.preferred_consultation_language)
            return {
                    "success": True,
                    "message": "Report sent via Email"
                }