"""
Twilio Webhook Endpoints

Handles incoming messages from Twilio webhooks.
"""

from fastapi import APIRouter, Request
import logging
from fastapi.responses import PlainTextResponse
from models.user import User
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from scripts.medication_utils import update_med_logs
from scripts.utils import generate_medication_whatsapp_response_message
from fastapi import Response


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

