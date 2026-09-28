from models.organization import TemplateTypeEnum, TwilioWhatsappTemplates
from .mcp_instance import mcp
from datetime import time
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses, QuestionTranslations
from models.user import User
from sqlalchemy.orm import selectinload
from sqlalchemy import distinct, select, func
from core.database import get_async_session
from enum import Enum
from sqlalchemy import false
from services.helpers import construct_whatsapp_brain_coach_message, generate_random_string
from services.whatsapp_service import whatsapp_service
from services.email_service import email_service
from scripts.utils import LANGUAGE_MAP, get_iso_language
import logging
from typing import Dict, List, Optional
from .base import MCPBaseModel


logger = logging.getLogger(__name__)

class QuestionType(str, Enum):
    trivia = "trivia"
    cognitive_assessment = "cognitive_assessment"
    chess = "chess"
    memory = 'memory'
    games = 'games' 

class RetrieveQuestionsInput(MCPBaseModel):
    user_id: int
    questions_type: QuestionType
    # session_id: Optional[str] = None

class RetrieveQuestionsOutput(MCPBaseModel):
    session_id: str = None
    questions: list[dict]

@mcp.tool(
    name="retrieve_questions",
    description=(
        "You will use this tool to retrieve the questions for a brain coach session."
        "You will call this tool when You're about to start the brain coach session."
        "the question type will always be enum. if the user wants cognitive excercises then question_type will be cognitive_assessment. "
        "if the user wants trivia then question_type will be trivia. "
        "if the user wants chess questions then the question_type will be chess. "
        "if the user wants memory questions then the question_type will be memory. "
        "if the user wants games questions then the question_type will be games. "
        "ALWAYS LEAVE session_id None to start a new session - a session_id will be returned. "
        "Leave session_id empty to start a new session - a session_id will be returned. "
        "If the user wants MORE questions within the session that is already in progress (they already have a session_id from a previous call to this tool), "
        "pass that exact same session_id back in to fetch additional questions under that same session instead of starting a new one."
        "If a user wants a different question type, they will start a new session and a new session_id will be returned."
        "The passed session_id is validated against the passed question_type - if it doesn't belong to this user, or belongs to a different question_type, a new session_id is generated instead."
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

        if input.questions_type.value == QuestionType.cognitive_assessment.value:
            target_session = session_count + 1
        else:
            target_session = 1

        print(target_session)

        stmt = (
            select(distinct(BrainCoachResponses.question_id))
            .join(BrainCoachQuestions, BrainCoachResponses.question_id == BrainCoachQuestions.id)
            .where(
                BrainCoachResponses.user_id == input.user_id,
                BrainCoachQuestions.category == input.questions_type.value
            )
            .order_by(BrainCoachResponses.question_id)
        )
        
        result = await db.execute(stmt)
        answered_question_ids = result.scalars().all()

        user_result = await db.execute(
            select(User).where(User.id == input.user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return {
                "success": False,
                "message": "user not found"
            }
        
        iso_language = get_iso_language(user.preferred_consultation_language)

        print('category:', input.questions_type.value, 'language:', iso_language, 'session:', target_session, 'answered_question_ids:', answered_question_ids)

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
                QuestionTranslations.language == iso_language,
                # BrainCoachQuestions.session == target_session,
                BrainCoachQuestions.id.not_in(answered_question_ids)
            )
            .order_by(BrainCoachQuestions.id)
            .limit(6)
        )
        
        if answered_question_ids:
            stmt = stmt.where(
                BrainCoachQuestions.id.not_in(answered_question_ids)
            )

        result = await db.execute(stmt)
        rows = result.all()

        memory_row = None
        other_rows = []
        
        for row in rows:
            if row.question_type in ("Memory", "Memoria", "Gedächtnis"):
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

        # session_id = input.session_id
        # if session_id:
        #     stmt = (
        #         select(BrainCoachQuestions.category)
        #         .join(BrainCoachResponses, BrainCoachResponses.question_id == BrainCoachQuestions.id)
        #         .where(
        #             BrainCoachResponses.session_id == session_id,
        #             BrainCoachResponses.user_id == input.user_id,
        #         )
        #         .limit(1)
        #     )
        #     result = await db.execute(stmt)
        #     existing_category = result.scalar_one_or_none()

        #     if existing_category != input.questions_type.value:
        #         session_id = None

        session_id = generate_random_string(8)

        return {
            "session_id": session_id,
            "questions": questions
        }

class RetrieveQuestionsInputV2(MCPBaseModel):
    user_id: int
    questions_type: QuestionType
    session_id: str

class RetrieveQuestionsOutputV2(MCPBaseModel):
    session_id: str = None
    questions: list[dict]
    
@mcp.tool(
    name="retrieve_questions_v2",
    description=(
        "You will use this tool to retrieve additional questions for an existing brain coach session."
        "This is the V2 variant of the question retrieval tool."
        "You will call this tool when a brain coach session is already in progress and additional questions are needed."
        "The question type will always be an enum."
        "If the user wants cognitive exercises then question_type will be cognitive_assessment."
        "If the user wants trivia then question_type will be trivia."
        "If the user wants chess questions then question_type will be chess."
        "If the user wants memory questions then question_type will be memory."
        "If the user wants games questions then question_type will be games."
        "ALWAYS provide the exact session_id from the previous question retrieval call."
        "Do NOT leave session_id empty or None."
        "Do NOT generate, modify, or substitute a session_id."
        "This tool is only for retrieving additional questions within an existing session."
        "If the user wants MORE questions of the same type, pass the exact same session_id back to retrieve additional questions under that same session."
        "If the user wants a different question type, do NOT use this tool to start a new session. The original question retrieval tool must be used to start the new session with session_id empty."
        "The passed session_id must belong to the current user and match the requested question_type."
        "Never use a session_id from a different user or a different question type."
    )
)    

async def retrieve_questions_v2(input: RetrieveQuestionsInputV2) -> RetrieveQuestionsOutputV2:
    async with get_async_session() as db:

        stmt = (
            select(func.count(func.distinct(BrainCoachResponses.session_id)))
            .where(BrainCoachResponses.user_id == input.user_id)
        )

        result = await db.execute(stmt)
        session_count = result.scalar_one()

        if input.questions_type.value == QuestionType.cognitive_assessment.value:
            target_session = session_count + 1
        else:
            target_session = 1

        stmt = (
            select(distinct(BrainCoachResponses.question_id))
            .join(BrainCoachQuestions, BrainCoachResponses.question_id == BrainCoachQuestions.id)
            .where(
                BrainCoachResponses.user_id == input.user_id,
                BrainCoachQuestions.category == input.questions_type.value
            )
            .order_by(BrainCoachResponses.question_id)
        )
        
        result = await db.execute(stmt)
        answered_question_ids = result.scalars().all()

        user_result = await db.execute(
            select(User).where(User.id == input.user_id)
        )
        user = user_result.scalar_one_or_none()

        if not user:
            return {
                "success": False,
                "message": "user not found"
            }
        
        iso_language = get_iso_language(user.preferred_consultation_language)

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
                QuestionTranslations.language == iso_language,
                BrainCoachQuestions.session == target_session,
                # BrainCoachQuestions.id.not_in(answered_question_ids)
            )
            .order_by(BrainCoachQuestions.id)
            .limit(6)
        )
        
        if answered_question_ids:
            stmt = stmt.where(
                BrainCoachQuestions.id.not_in(answered_question_ids)
            )

        result = await db.execute(stmt)
        rows = result.all()

        memory_row = None
        other_rows = []
        
        for row in rows:
            if row.question_type in ("Memory", "Memoria", "Gedächtnis"):
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

        return {
            "session_id": input.session_id,
            "questions": questions
        }

class AnswerItem(MCPBaseModel):
    question_id: int
    score: int
    user_answer: str


class StoreSessionAnswersInput(MCPBaseModel):
    session_id: str
    user_id: int
    answers: List[AnswerItem]


@mcp.tool(
    name="store_session_answers",
    description=(
        "Store all answers for a completed brain coach session at once. "
        "Call this tool only after the user finishes the full session."
        "the answers should be in the following format:" \
        "[{"
        "question_id,"
        "score,"
        "user_answer"
        "}," \
        "{"
        "question_id,"
        "score,"
        "user_answer"
        "}]"
    )
)
async def store_session_answers(input: StoreSessionAnswersInput) -> dict:
    try:
        async with get_async_session() as db:
            responses = [
                BrainCoachResponses(
                    session_id=input.session_id,
                    user_id=input.user_id,
                    question_id=answer.question_id,
                    score=answer.score,
                    user_answer=answer.user_answer
                )
                for answer in input.answers
            ]

            db.add_all(responses)
            await db.commit()

            return {
                "success": True,
                "stored_count": len(responses)
            }

    except Exception as e:
        logger.error(f"Error storing session answers: {e}")
        return {
            "success": False
        }

        
class SendBrainCoachReportInput(MCPBaseModel):
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
        if preferred_report_channel not in ['email', 'whatsapp']:
            user.preferred_reports_channel = 'whatsapp'
            await db.commit()

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
                    
                whatsapp_content = construct_whatsapp_brain_coach_message(user.first_name, report_content, input.agent_notes_and_suggestions, input.question_type.value)
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
        

from pydantic import BaseModel
from typing import List, Literal, Optional
from collections import defaultdict
import statistics

class BrainCoachTrendInput(MCPBaseModel):
    user_id: int

class ThemeTrend(MCPBaseModel):
    last_3: List[int]
    trend: Literal["improving", "declining", "stable"]


class BrainCoachTrendOutput(MCPBaseModel):
    sessions_total: int
    last_session_percent: Optional[int]
    last_5_session_percents: List[int]
    moving_avg_5: Optional[float]
    trend_direction: Literal[
        "improving",
        "declining",
        "stable",
        "insufficient_data"
    ]
    delta_last_vs_prev: Optional[int]
    consistency_stddev: Optional[float]
    # theme_trends: Dict[str, ThemeTrend]


@mcp.tool(
    name="get_brain_coach_trends",
    description="Returns performance statistics and trends for a user's brain coach sessions."
)
async def get_brain_coach_trends(input: BrainCoachTrendInput) -> BrainCoachTrendOutput:
    async with get_async_session() as db:

        # Fetch responses + related question
        result = await db.execute(
            select(BrainCoachResponses)
            .where(BrainCoachResponses.user_id == input.user_id)
            .options(selectinload(BrainCoachResponses.question))
            .order_by(BrainCoachResponses.created.asc())
        )

        responses = result.scalars().all()

        if not responses:
            return BrainCoachTrendOutput(
                sessions_total=0,
                last_session_percent=None,
                last_5_session_percents=[],
                moving_avg_5=None,
                trend_direction="insufficient_data",
                delta_last_vs_prev=None,
                consistency_stddev=None,
                theme_trends={}
            )

        # --------------------------
        # GROUP BY SESSION
        # --------------------------
        sessions = defaultdict(list)
        for r in responses:
            sessions[r.session_id].append(r)

        session_percents = []
        # theme_session_scores = defaultdict(list)

        for session_id in sorted(sessions.keys()):
            session_items = sessions[session_id]

            total_score = sum(r.score for r in session_items)
            max_score = sum(r.question.max_score or 1 for r in session_items)

            percent = round((total_score / max_score) * 100)
            session_percents.append(percent)

            # THEME breakdown
            # theme_totals = defaultdict(lambda: {"score": 0, "max": 0})

            # for r in session_items:
            #     theme = r.question.category or "General"
            #     theme_totals[theme]["score"] += r.score
            #     theme_totals[theme]["max"] += r.question.max_score or 1

            # for theme, values in theme_totals.items():
            #     theme_percent = round((values["score"] / values["max"]) * 100)
            #     theme_session_scores[theme].append(theme_percent)

        # --------------------------
        # OVERALL METRICS
        # --------------------------
        sessions_total = len(session_percents)
        last_session_percent = session_percents[-1]

        last_5 = session_percents[-5:]
        moving_avg_5 = round(sum(last_5) / len(last_5), 1)

        delta_last_vs_prev = None
        trend_direction = "insufficient_data"

        if sessions_total >= 2:
            delta_last_vs_prev = session_percents[-1] - session_percents[-2]

            if delta_last_vs_prev > 1:
                trend_direction = "improving"
            elif delta_last_vs_prev < -1:
                trend_direction = "declining"
            else:
                trend_direction = "stable"

        consistency_stddev = None
        if sessions_total >= 2:
            consistency_stddev = round(statistics.pstdev(session_percents), 1)

        # --------------------------
        # THEME TRENDS
        # --------------------------
        # theme_trends = {}

        # for theme, scores in theme_session_scores.items():
        #     if len(scores) < 2:
        #         continue

        #     last_3 = scores[-3:]

        #     if len(last_3) >= 2:
        #         delta = last_3[-1] - last_3[0]

        #         if delta > 2:
        #             trend = "improving"
        #         elif delta < -2:
        #             trend = "declining"
        #         else:
        #             trend = "stable"
        #     else:
        #         trend = "stable"

        #     theme_trends[theme] = ThemeTrend(
        #         last_3=last_3,
        #         trend=trend
        #     )

        print(sessions_total, last_session_percent, last_5, moving_avg_5, trend_direction, delta_last_vs_prev, consistency_stddev)

        return BrainCoachTrendOutput(
            sessions_total=sessions_total,
            last_session_percent=last_session_percent,
            last_5_session_percents=last_5,
            moving_avg_5=moving_avg_5,
            trend_direction=trend_direction,
            delta_last_vs_prev=delta_last_vs_prev,
            consistency_stddev=consistency_stddev,
            # theme_trends=theme_trends
        )
