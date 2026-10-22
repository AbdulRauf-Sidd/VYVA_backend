from fastapi import APIRouter, Request, Depends, HTTPException, Response, Query, status
import hashlib
import hmac
import json
import logging
from fastapi.responses import PlainTextResponse
from models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.database import get_db
from core.config import settings
from scripts.medication_utils import update_med_logs
from scripts.utils import generate_medication_whatsapp_response_message, get_iso_language, generate_reminder_later_whatsapp_response_message, get_user_local_dt, is_doctor_available
from models.organization import TemplateTypeEnum, TwilioWhatsappTemplates
from models.medication import MedicationLog
from services.helpers import construct_general_welcome_message, construct_welcome_message_for_main_agent
from services.whatsapp_service import whatsapp_service
from scripts.medication_utils import build_medication_payload
from tasks.utils import schedule_reminder_message
from datetime import datetime, timedelta, timezone
from services.whatsapp_service import whatsapp_service
from schemas.twilio import TwilioPersonalizationRequest


logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/incoming-message")
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification handshake (runs when the callback URL is saved in the Meta app dashboard)."""
    if hub_mode == "subscribe" and settings.WHATSAPP_VERIFY_TOKEN and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


def _valid_signature(raw_body: bytes, signature_header: str | None) -> bool:
    """Validate X-Hub-Signature-256. Fails closed: without WHATSAPP_APP_SECRET every webhook is rejected."""
    if not settings.WHATSAPP_APP_SECRET:
        logger.error("WHATSAPP_APP_SECRET is not configured - rejecting webhook")
        return False
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(settings.WHATSAPP_APP_SECRET.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header[len("sha256="):])


def _extract_button_payloads(body: dict) -> list[tuple[str, str]]:
    """Return (phone_number, button_payload) for each button reply in a Meta webhook body."""
    results = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            for message in change.get("value", {}).get("messages", []):
                sender = message.get("from")
                payload = None
                if message.get("type") == "button":
                    payload = (message.get("button") or {}).get("payload")
                elif message.get("type") == "interactive":
                    payload = ((message.get("interactive") or {}).get("button_reply") or {}).get("id")
                if sender and payload:
                    results.append((f"+{sender}", payload))
    return results


async def _handle_button_payload(db: AsyncSession, phone_number: str, button_payload: str) -> str | None:
    """Process one quick-reply button press. Returns a text reply to send back, if any."""
    user_result = await db.execute(
        select(User).where(User.phone_number == phone_number)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        logger.warning(f"Button reply from unknown number {phone_number}")
        return None

    ## QUICK REPLY
    payload = button_payload.split(":")
    if len(payload) < 2:
        logger.warning(f"Unexpected ButtonPayload format: {button_payload}")
        return None

    action = payload[0]
    template_type = payload[-1]
    reminder_ids = payload[1]
    med_log_ids = [int(x.strip()) for x in reminder_ids.split(",")]
    if template_type == TemplateTypeEnum.ask_for_reminder.value:
        if action == "Yes":
            stmt = (
                select(MedicationLog)
                .where(MedicationLog.id.in_(med_log_ids), MedicationLog.user_id == user.id)
                .options(
                    selectinload(MedicationLog.medication),
                    selectinload(MedicationLog.medication_time),
                )
            )

            result = await db.execute(stmt)
            logs = result.scalars().all()
            meds = []
            for log in logs:
                medication = log.medication
                medication_time = log.medication_time
                medication_payload = build_medication_payload(medication, medication_time)
                meds.append(medication_payload)

            reminder_payload = {
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone_number': user.phone_number,
                'language': user.preferred_consultation_language,
                'user_id': user.id,
                "medications": meds
            }

            dt_utc = datetime.now(timezone.utc) + timedelta(minutes=15)
            schedule_reminder_message(reminder_payload, dt_utc=dt_utc, preferred_reminder_channel='whatsapp')

        return generate_reminder_later_whatsapp_response_message(user.preferred_consultation_language, action)

    if template_type == TemplateTypeEnum.medication_reminder.value:
        medication_taken = (action == "Yes")

        update_med_logs(user.id, medication_taken, med_log_ids)
        if not medication_taken:
            template_result = await db.execute(
                select(TwilioWhatsappTemplates.template_id).where(TwilioWhatsappTemplates.language == user.preferred_consultation_language, TwilioWhatsappTemplates.template_type == TemplateTypeEnum.ask_for_reminder.value)
            )
            template_id = template_result.scalar_one_or_none()

            # The "ask for reminder" template only carries its buttons; each button returns "<Yes|No>:<log ids>:<type>".
            ask_type = TemplateTypeEnum.ask_for_reminder.value
            await whatsapp_service.send_message(
                user.phone_number,
                template_id=template_id,
                template_data={},
                language=user.preferred_consultation_language,
                quick_reply_payloads=[f"Yes:{reminder_ids}:{ask_type}", f"No:{reminder_ids}:{ask_type}"],
            )
            return None

        return generate_medication_whatsapp_response_message(user.preferred_consultation_language, medication_taken)

    logger.warning(f"Unhandled ButtonPayload: {button_payload}")
    return None


@router.post("/incoming-message")
async def receive_incoming_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook endpoint for incoming WhatsApp messages (Meta WhatsApp Business Cloud API).
    Meta sends JSON; delivery-status events arrive here too and are ignored.
    Always answers 200 for authentic requests so Meta does not keep retrying.
    """
    raw_body = await request.body()
    if not _valid_signature(raw_body, request.headers.get("X-Hub-Signature-256")):
        logger.warning("WhatsApp webhook rejected: invalid signature")
        raise HTTPException(status_code=403, detail="Invalid signature")

    try:
        body = json.loads(raw_body or b"{}")
        for phone_number, button_payload in _extract_button_payloads(body):
            try:
                reply = await _handle_button_payload(db, phone_number, button_payload)
                if reply:
                    await whatsapp_service.send_simple_message(phone_number, reply)
            except Exception as e:
                logger.error(f"Error processing ButtonPayload {button_payload!r}: {e}")
    except Exception as e:
        logger.exception(f"Error processing WhatsApp webhook: {e}")

    return Response(status_code=200)


@router.post("/personalization")
async def personalize_call(
    payload: TwilioPersonalizationRequest,
    db: AsyncSession = Depends(get_db)
):
    caller_id = payload.caller_id
    if not caller_id.startswith('+'):
        caller_id = '+' + caller_id
    stmt = select(User).where(User.phone_number == caller_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    local_time = get_user_local_dt(user.timezone) if user and user.timezone else ""

    if not user:
        return {
            "dynamic_variables": {
                "user_id": "",
                "address": "",
                "first_name": "",
                "name": "",
                'email': "",
                "phone_number": payload.caller_id,
                "local_time": "",
                "timezone": "",
                'preferred_reports_channel': "",
                'health_conditions': "",
                'mobility_issues': "",
                "conversation_id": payload.conversation_id,
                "is_registered": False,
                "app_user": False,
                "doctor_available": is_doctor_available(None)
            },
        }

    first_time = not bool(user.social_companion_first_time)
    
    iso_language = get_iso_language(user.preferred_consultation_language)
    first_message = construct_welcome_message_for_main_agent(user.first_name, iso_language, first_time)

    address = user.full_address
    email = user.email
    timezone = user.timezone

    logger.info(f"address: {address}, email: {email}, timezone: {timezone}")


    return {
        "conversation_config_override": {
            "agent": {
                "first_message": first_message,
            }
        },
        "dynamic_variables": {
            "user_id": user.id,
            "address": user.full_address,
            "first_name": user.first_name,
            "name": user.full_name,
            "local_time": local_time.time().strftime("%H:%M") if local_time else "",
            'email': user.email,
            "phone_number": user.phone_number,
            'preferred_reports_channel': user.preferred_reports_channel,
            'health_conditions': user.health_conditions,
            'mobility_issues': user.mobility,
            "timezone": timezone,
            "conversation_id": payload.conversation_id,
            "is_registered": True,
            "app_user": False,
            "doctor_available": is_doctor_available(timezone)
        },
    }


@router.post("/rc/personalization")
async def personalize_call(
    payload: TwilioPersonalizationRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.phone_number == payload.caller_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    local_time = get_user_local_dt(user.timezone) if user and user.timezone else ""

    if not user:
        return {
        "dynamic_variables": {
            "user_id": "",
            "first_name": "",
            "name": "",
            "phone_number": payload.caller_id,
            'email': "",
            "local_time": "",
            "timezone": "",
            'preferred_reports_channel': "",
            'health_conditions': "",
            'mobility_issues': "",
            "conversation_id": payload.conversation_id,
            "is_registered": False,
            "app_user": False
        },
    }

    first_time = not bool(user.social_companion_first_time)
    
    iso_language = get_iso_language(user.preferred_consultation_language)
    first_message = construct_welcome_message_for_main_agent(user.first_name, iso_language, first_time)


    return {
        "conversation_config_override": {
            "agent": {
                "first_message": first_message,
            }
        },
        "dynamic_variables": {
            "user_id": user.id,
            "address": user.full_address,
            "first_name": user.first_name,
            "name": user.full_name,
            "local_time": local_time.time().strftime("%H:%M") if local_time else "",
            'email': user.email,
            "phone_number": user.phone_number,
            'preferred_reports_channel': user.preferred_reports_channel,
            'health_conditions': user.health_conditions,
            'mobility_issues': user.mobility,
            "timezone": user.timezone,
            "conversation_id": payload.conversation_id,
            "is_registered": True,
            "app_user": False
        },
    }