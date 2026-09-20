"""
Ad-hoc manual test functions. Not run via pytest - call these directly,
e.g.:

    python -c "from scripts.tests import test_send_weekly_brain_coach_report; test_send_weekly_brain_coach_report(1)"
    python -c "from scripts.tests import test_send_session_brain_coach_report; test_send_session_brain_coach_report(1)"
"""

import logging

from core.database import get_sync_session
from models.user import User
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses, QuestionTranslations
from models.organization import TemplateTypeEnum, TwilioWhatsappTemplates
from scripts.utils import LANGUAGE_MAP, get_user_local_dt
from tasks.brain_coach_tasks import build_weekly_brain_coach_report
from services.helpers import construct_whatsapp_brain_coach_message
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)

TEST_WHATSAPP_NUMBER = "+923152526525"


def _send_whatsapp_report(db, user: User, template_type: str, whatsapp_content: dict):
    template = (
        db.query(TwilioWhatsappTemplates)
        .filter(
            TwilioWhatsappTemplates.template_type == template_type,
            TwilioWhatsappTemplates.language == user.preferred_consultation_language,
        )
        .first()
    )

    if not template:
        logger.error(
            f"No WhatsApp template found for type {template_type}, "
            f"language {user.preferred_consultation_language}"
        )
        return

    whatsapp_service.send_message_sync(
        to_phone=TEST_WHATSAPP_NUMBER,
        template_data=whatsapp_content,
        template_id=template.template_id,
    )

    logger.info(f"Sent {template_type} report for user {user.id} to {TEST_WHATSAPP_NUMBER}")


def test_send_weekly_brain_coach_report(user_id: int):
    """
    Builds the weekly brain coach report for the given user and sends it to
    a hardcoded WhatsApp number, regardless of the user's own phone number
    or preferred_reports_channel.
    """
    with get_sync_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return

        local_dt = get_user_local_dt(user.timezone)
        template_type, whatsapp_content, _report_content, _week_start, _week_end = (
            build_weekly_brain_coach_report(db, user, local_dt)
        )

        _send_whatsapp_report(db, user, template_type, whatsapp_content)


def test_send_session_brain_coach_report(user_id: int):
    """
    Builds the report for the user's most recent brain coach session and
    sends it to a hardcoded WhatsApp number, regardless of the user's own
    phone number or preferred_reports_channel.
    """
    with get_sync_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"User {user_id} not found")
            return

        latest_session_id = (
            db.query(BrainCoachResponses.session_id)
            .filter(BrainCoachResponses.user_id == user_id)
            .order_by(BrainCoachResponses.created.desc())
            .limit(1)
            .scalar()
        )

        if not latest_session_id:
            logger.error(f"No brain coach sessions found for user {user_id}")
            return

        responses = (
            db.query(BrainCoachResponses)
            .filter(
                BrainCoachResponses.user_id == user_id,
                BrainCoachResponses.session_id == latest_session_id,
            )
            .order_by(BrainCoachResponses.created.desc())
            .all()
        )

        question_ids = [response.question_id for response in responses]
        iso_language = LANGUAGE_MAP.get(
            (user.preferred_consultation_language or "english").lower(), "en"
        )

        questions = (
            db.query(BrainCoachQuestions, QuestionTranslations)
            .join(QuestionTranslations, BrainCoachQuestions.id == QuestionTranslations.question_id)
            .filter(
                BrainCoachQuestions.id.in_(question_ids),
                QuestionTranslations.language == iso_language,
            )
            .order_by(BrainCoachQuestions.id)
            .all()
        )

        report_content = []
        category = None
        for question, translation in questions:
            for response in responses:
                if question.id != response.question_id:
                    continue

                category = category or question.category
                report_content.append({
                    "question_text": translation.question_text,
                    "question_type": translation.question_type,
                    "theme": translation.theme,
                    "score": response.score,
                    "max_score": question.max_score,
                    "tier": question.tier,
                    "session": question.session,
                })

        whatsapp_content = construct_whatsapp_brain_coach_message(
            user.first_name,
            report_content,
            "Great job this session - keep it up!",
            category,
        )

        _send_whatsapp_report(db, user, TemplateTypeEnum.brain_coach.value, whatsapp_content)
