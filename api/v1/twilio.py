from fastapi import APIRouter, Request, Depends, HTTPException, Response, status
import logging
from fastapi.responses import PlainTextResponse
from models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.database import get_db
from core.config import settings
from scripts.medication_utils import update_med_logs
from scripts.utils import generate_medication_whatsapp_response_message, get_iso_language, generate_reminder_later_whatsapp_response_message
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
        
        whatsapp_number = form.get("From")
        phone_number = whatsapp_number.replace("whatsapp:", "")
        user_result = await db.execute(
            select(User).where(User.phone_number == phone_number)
        )
        user = user_result.scalar_one_or_none()

        ## QUICK REPLY
        try:
            payload = button_payload.split(":")
            if len(payload) < 2:
                logger.warning(f"Unexpected ButtonPayload format: {button_payload}")
                return Response(status_code=200)
            
            action = payload[0]
            template_type = payload[-1]
            reminder_ids = payload[1]
            med_log_ids = [int(x.strip()) for x in reminder_ids.split(",")]
            if template_type == TemplateTypeEnum.ask_for_reminder.value:
                if action == "Yes":
                    stmt = (
                        select(MedicationLog)
                        .where(MedicationLog.id.in_(med_log_ids))
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
                    
                    payload = {
                        'first_name': user.first_name,
                        'last_name': user.last_name,
                        'phone_number': user.phone_number,
                        'language': user.preferred_consultation_language,
                        'user_id': user.id,
                        "medications": meds
                    }

                    dt_utc = datetime.now(timezone.utc) + timedelta(minutes=15) 
                    schedule_reminder_message(payload, dt_utc=dt_utc, preferred_reminder_channel='whatsapp')
                    
                response_message = generate_reminder_later_whatsapp_response_message(user.preferred_consultation_language, action)
                return PlainTextResponse(response_message)
            if template_type == TemplateTypeEnum.medication_reminder.value:
                reminder_id = payload[1]
                med_log_ids = [int(x.strip()) for x in reminder_id.split(",")]
                medication_taken = (action == "Yes")
                
                update_med_logs(user.id, medication_taken, med_log_ids)
                if not medication_taken:
                    template_result = await db.execute(
                        select(TwilioWhatsappTemplates.template_id).where(TwilioWhatsappTemplates.language == user.preferred_consultation_language, TwilioWhatsappTemplates.template_type == TemplateTypeEnum.ask_for_reminder.value)
                    )
                    template_id = template_result.scalar_one_or_none()

                    template_data = {
                        "1": reminder_id,
                        "2": TemplateTypeEnum.ask_for_reminder.value
                    }
                    await whatsapp_service.send_message(user.phone_number, template_id=template_id, template_data=template_data)
                    return Response(status_code=200)
                
                response_message = generate_medication_whatsapp_response_message(user.preferred_consultation_language, medication_taken)
                if response_message:
                    return PlainTextResponse(response_message)
            

            logger.warning(f"Unhandled ButtonPayload: {button_payload}")
            return Response(status_code=200)
        
        except Exception as e:
            logger.error(f"Error processing ButtonPayload: {e}")
            return Response(status_code=200)
                
    except Exception as e:
        logger.exception(f"Error processing Twilio webhook: {e}")
        return {
            "status": "error",
            "message": str(e)
        }


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

    first_time = user.social_companion_first_time
    iso_language = get_iso_language(user.preferred_consultation_language)
    first_message = construct_welcome_message_for_main_agent(user.first_name, iso_language, first_time)


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
            "conversation_id": payload.conversation_id,
            "app_user": False
        },
    }