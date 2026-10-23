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


def test_brain_coach_outbound_call(user_id: int):
    """
    Fires a brain coach outbound call for a user, bypassing check-in scheduling.
    Prints each step so you can see where it fails.

    python -c "from scripts.tests import test_brain_coach_outbound_call; test_brain_coach_outbound_call(1)"
    """
    from sqlalchemy.orm import selectinload
    from core.database import SessionLocal
    from models.organization import Organization, AgentTypeEnum
    from scripts.utils import generate_brain_coach_conversation_plan
    from services.elevenlabs_service import make_brain_coach_call
    from services.helpers import construct_user_dynamic_variables

    db = SessionLocal()
    try:
        user = (
            db.query(User)
            .options(selectinload(User.organization).selectinload(Organization.agents))
            .filter(User.id == user_id)
            .first()
        )
        if not user:
            print(f"User {user_id} not found")
            return

        agent_id = next(
            (a.agent_id for a in user.organization.agents if a.agent_type == AgentTypeEnum.brain_coach.value),
            None,
        )
        print(f"user={user.id} phone={user.phone_number} lang={user.preferred_consultation_language} "
              f"org={user.organization.id} phone_number_id={user.organization.phone_number_id} agent_id={agent_id}")
        if not agent_id:
            print("No brain coach agent found for this user's organization")
            return

        payload = {
            "user_id": user.id,
            "agent_id": agent_id,
            "first_name": user.first_name,
            "phone_number": user.phone_number,
            "language": user.preferred_consultation_language,
            "phone_number_id": user.organization.phone_number_id,
        }
        payload = {**construct_user_dynamic_variables(user), **payload}

        try:
            plan = generate_brain_coach_conversation_plan(user)
            if plan:
                payload["conversation_plan"] = plan
            print(f"conversation plan generated: {bool(plan)}")
        except Exception as e:
            print(f"conversation plan failed (continuing without): {e}")

        response = make_brain_coach_call(payload)
        print(f"ElevenLabs response: {response}")
        if response is None:
            print("Call failed - see logs / OutboundCallLog for the error")
    finally:
        db.close()


def test_send_onboarding_whatsapp(user_id: int):
    """
    Sends the onboarding magic link WhatsApp (via Meta) to a user. Creates a real
    temp token and sends to the user's real number. Caregiver SMS is not sent.

    python -c "from scripts.tests import test_send_onboarding_whatsapp; test_send_onboarding_whatsapp(1)"
    """
    from scripts.onboarding_utils import send_onboarding_sms

    with get_sync_session() as db:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            print(f"User {user_id} not found")
            return
        phone = user.phone_number
        print(f"user={user.id} phone={phone} lang={user.preferred_consultation_language} org={user.organization_id}")

    try:
        link = send_onboarding_sms(phone_number=phone, send_to_caregiver=False)
        print(f"Sent. Base link: {link}")
    except Exception as e:
        print(f"Failed: {e}")
