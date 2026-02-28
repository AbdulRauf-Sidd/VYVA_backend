"""
Twilio Webhook Endpoints

Handles incoming messages from Twilio webhooks and outbound WhatsApp (e.g. emergency).
"""

from fastapi import APIRouter, Request, Depends, HTTPException, Response, status
import logging
from fastapi.responses import PlainTextResponse
from models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.config import settings
from scripts.medication_utils import update_med_logs
from scripts.utils import generate_medication_whatsapp_response_message, get_iso_language

from pydantic import BaseModel
from services.helpers import construct_general_welcome_message
from services.whatsapp_service import WhatsAppService


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/incoming-message")
async def receive_incoming_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook endpoint for Twilio incoming messages.
    Receives POST requests from Twilio when a message is received.
    
    Twilio sends form-encoded data (application/x-www-form-urlencoded),
    so we need to handle it as form data.
    """
    try:
        form = await request.form()
        
        button_payload = form.get("ButtonPayload")
        if not button_payload:
            return Response(status_code=200)
        
        action, reminder_id = button_payload.split(":")
        med_log_ids = [int(x.strip()) for x in reminder_id.split(",")]
        medication_taken = (action == "Yes")
        
        whatsapp_number = form.get("From")
        phone_number = whatsapp_number.replace("whatsapp:", "")
        user_result = await db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        user = user_result.scalar_one_or_none()

        update_med_logs(user.id, medication_taken, med_log_ids)

        response_message = generate_medication_whatsapp_response_message(user.preferred_consultation_language, medication_taken)
        if response_message:
            return PlainTextResponse(response_message)    
        
        return PlainTextResponse("OK")
                
    except Exception as e:
        logger.exception(f"Error processing Twilio webhook: {e}")
        return {
            "status": "error",
            "message": str(e)
        }

class SendEmergencyWhatsAppRequest(BaseModel):
    """Request body for sending an emergency WhatsApp via Twilio template."""

    To: str  # Recipient; will be normalized to whatsapp:+... if needed
    From: str  # Sender (Twilio WhatsApp number); same normalization
    Body: str  # Maps to template variable {{2}} (e.g. symptom/description)
    user_name: str  # Maps to template variable {{1}}


class TwilioPersonalizationRequest(BaseModel):
    caller_id: str
    conversation_id: str


@router.post("/personalization")
async def personalize_call(
    payload: TwilioPersonalizationRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.phone_number == payload.caller_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    iso_language = get_iso_language(user.preferred_consultation_language)
    first_message = construct_general_welcome_message(user.first_name, iso_language)


    return {
        "conversation_config_override": {
            "agent": {
                "first_message": first_message,
            }
            # "tts": {
            #   "voice_id": "new-voice-id"
            # }
        },
        "dynamic_variables": {
            "user_id": user.id,
            "first_name": user.first_name,
            "phone_number": user.phone_number,
            "timezone": user.timezone,
            "conversation_id": payload.conversation_id
        },
    }


@router.post("/send-emergency-whatsapp", status_code=status.HTTP_200_OK)
async def send_emergency_whatsapp(payload: SendEmergencyWhatsAppRequest):
    """
    Send an emergency WhatsApp message using the Twilio template.

    Template: 🚨 EMERGENCIA: {{1}} está experimentando {{2}}. Llamada transferida al 112. Por favor, contacte inmediatamente.
    - {{1}} = user_name
    - {{2}} = Body (symptom/description from request)
    """
    to_phone = (payload.To or "").strip()
    from_phone = (payload.From or "").strip()
    if not to_phone or not from_phone:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="To and From are required.",
        )
    if not payload.user_name or not (payload.Body or "").strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_name and Body are required.",
        )

    content_variables = {
        "1": payload.user_name.strip(),
        "2": (payload.Body or "").strip(),
    }
    template_sid = settings.TWILIO_WHATSAPP_EMERGENCY_TEMPLATE_SID

    whatsapp_service = WhatsAppService()
    success = await whatsapp_service.send_emergency_template(
        to_phone=to_phone,
        from_phone=from_phone,
        content_sid=template_sid,
        content_variables=content_variables,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to send emergency WhatsApp via Twilio.",
        )
    return {
        "message": "Emergency WhatsApp sent successfully",
        "success": True,
    }