import logging
from datetime import datetime, time, timedelta

from sqlalchemy import select, false

from celery_app import celery_app
from core.database import get_sync_session
from models.user import User
from models.brain_coach import BrainCoachQuestions, BrainCoachResponses, QuestionTranslations
from models.organization import TemplateTypeEnum, TwilioWhatsappTemplates
from scripts.utils import LANGUAGE_MAP, get_user_local_dt
from services.helpers import (
    construct_whatsapp_weekly_brain_coach_message,
    construct_whatsapp_weekly_no_activity_message,
)
from services.whatsapp_service import whatsapp_service
from services.email_service import email_service
import asyncio

logger = logging.getLogger(__name__)


@celery_app.task(name="send_weekly_brain_coach_reports")
def send_weekly_brain_coach_reports():
    """
    Fires once a week (Monday 00:00 UTC). For each active user, builds and
    sends a report of their previous week's brain coach activity (across
    all game types) to their preferred channel. Delivery lands at whatever
    local hour that is for the user - not pinned to a specific local time.
    """
    with get_sync_session() as db:
        users = db.query(User).filter(User.is_active.is_(True)).all()

        for user in users:
            try:
                if not user.timezone:
                    continue

                local_dt = get_user_local_dt(user.timezone)
                _send_weekly_report_for_user(db, user, local_dt)
            except Exception as e:
                logger.error(f"Error sending weekly brain coach report for user {user.id}: {e}")


def build_weekly_brain_coach_report(db, user: User, local_dt: datetime):
    """
    Builds (but does not send) the previous week's brain coach report for a
    user. Returns (template_type, whatsapp_content, report_content,
    week_start_local, week_end_local).
    """
    week_end_local = datetime.combine(local_dt.date(), time.min, tzinfo=local_dt.tzinfo)
    week_start_local = week_end_local - timedelta(days=7)

    query = (
        select(BrainCoachResponses)
        .where(
            BrainCoachResponses.user_id == user.id,
            BrainCoachResponses.created >= week_start_local,
            BrainCoachResponses.created < week_end_local,
        )
        .order_by(BrainCoachResponses.created.desc())
    )
    responses = db.execute(query).scalars().all()

    if not responses:
        return (
            TemplateTypeEnum.brain_coach_weekly_no_activity.value,
            construct_whatsapp_weekly_no_activity_message(user.first_name, week_start_local, week_end_local),
            [],
            week_start_local,
            week_end_local,
        )

    question_ids = [response.question_id for response in responses]
    iso_language = LANGUAGE_MAP.get(
        (user.preferred_consultation_language or "english").lower(), "en"
    )

    query = (
        select(BrainCoachQuestions, QuestionTranslations)
        .join(
            QuestionTranslations,
            BrainCoachQuestions.id == QuestionTranslations.question_id,
        )
        .where(
            BrainCoachQuestions.id.in_(question_ids) if question_ids else false(),
            QuestionTranslations.language == iso_language,
        )
        .order_by(BrainCoachQuestions.id)
    )
    questions = db.execute(query).all()

    report_content = []
    category_totals = {}

    for question, translation in questions:
        for response in responses:
            if question.id != response.question_id:
                continue

            report_content.append({
                "question_text": translation.question_text,
                "question_type": translation.question_type,
                "theme": translation.theme,
                "score": response.score,
                "max_score": question.max_score,
                "tier": question.tier,
                "session": question.session,
            })

            category = question.category or "games"
            totals = category_totals.setdefault(category, {"score": 0, "max_score": 0, "sessions": set()})
            totals["score"] += response.score
            totals["max_score"] += question.max_score or 0
            totals["sessions"].add(response.session_id)

    category_breakdown = [
        {
            "category": category,
            "score": totals["score"],
            "max_score": totals["max_score"],
            "sessions": len(totals["sessions"]),
        }
        for category, totals in category_totals.items()
    ]

    whatsapp_content = construct_whatsapp_weekly_brain_coach_message(
        user.first_name, week_start_local, week_end_local, category_breakdown
    )

    return (
        TemplateTypeEnum.brain_coach_weekly_summary.value,
        whatsapp_content,
        report_content,
        week_start_local,
        week_end_local,
    )


def _send_weekly_report_for_user(db, user: User, local_dt: datetime):
    template_type, whatsapp_content, report_content, week_start_local, week_end_local = (
        build_weekly_brain_coach_report(db, user, local_dt)
    )

    _dispatch_report(
        db,
        user,
        template_type=template_type,
        whatsapp_content=whatsapp_content,
        report_content=report_content,
        week_start_local=week_start_local,
        week_end_local=week_end_local,
    )


def _dispatch_report(db, user: User, template_type, whatsapp_content, report_content, week_start_local, week_end_local):
    preferred_report_channel = user.preferred_reports_channel
    if preferred_report_channel not in ["email", "whatsapp"]:
        preferred_report_channel = "whatsapp"
        user.preferred_reports_channel = "whatsapp"
        db.commit()

    if preferred_report_channel == "whatsapp":
        phone_number = user.secondary_phone if user.is_primary_landline else user.phone_number

        if phone_number:
            template = (
                db.query(TwilioWhatsappTemplates)
                .filter(
                    TwilioWhatsappTemplates.template_type == template_type,
                    TwilioWhatsappTemplates.language == user.preferred_consultation_language,
                )
                .first()
            )
            whatsapp_template_id = template.template_id if template else None

            if not whatsapp_template_id:
                logger.warning(
                    f"No WhatsApp template found for type {template_type}, "
                    f"language {user.preferred_consultation_language}"
                )
                return _fallback_to_email(user, report_content, week_start_local, week_end_local)

            whatsapp_service.send_message_sync(
                to_phone=phone_number,
                template_data=whatsapp_content,
                template_id=whatsapp_template_id,
            )
            return

    _fallback_to_email(user, report_content, week_start_local, week_end_local)


def _fallback_to_email(user: User, report_content, week_start_local, week_end_local):
    if not user.email:
        logger.warning(f"No email or WhatsApp number available for user {user.id}, skipping weekly report.")
        return

    if not report_content:
        logger.info(f"Skipping no-activity email for user {user.id} (weekly no-activity emails not implemented).")
        return

    asyncio.run(
        email_service.send_brain_coach_report(
            user.email,
            report_content,
            user.full_name,
            f"Weekly summary for {week_start_local.strftime('%b %d')} - {week_end_local.strftime('%b %d, %Y')}",
            "1",
            language=user.preferred_consultation_language,
        )
    )
