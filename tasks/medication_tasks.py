from core.database import SessionLocal
from celery_app import celery_app
from services.whatsapp_service import whatsapp_service
from models import user
from services.elevenlabs_service import make_onboarding_call, make_medication_reminder_call
from models.user import User
from models.onboarding import OnboardingUser, OnboardingLogs
import logging
from sqlalchemy.orm import selectinload
from datetime import datetime
from sqlalchemy.orm import Session
from datetime import datetime, date
from zoneinfo import ZoneInfo
from models.medication import Medication, MedicationTime, MedicationStatus, MedicationLog
from models.organization import AgentTypeEnum, TwilioWhatsappTemplates, TemplateTypeEnum
from sqlalchemy import or_, select
from models.eleven_labs_sessions import ElevenLabsSessions
from scripts.medication_utils import notify_caretaker_on_missed_meds, construct_medication_string_for_whatsapp
from tasks.utils import schedule_celery_task_for_call_status_check, schedule_reminder_message, update_medication_status
import asyncio

# from scripts.utils import construct_onboarding_user_payload

from twilio.rest import Client
from core.config import settings

logger = logging.getLogger(__name__)

@celery_app.task(name="notify_caregiver_on_missed_medication_task")
def notify_caregiver_on_missed_medication_task(user_id: int):
    notify_caretaker_on_missed_meds(user_id)

@celery_app.task(name="send_whatsapp_medication_reminder", max_retries=0)
def send_whatsapp_medication_reminder(payload):
    try:
        user_id = payload.get("user_id")
        phone_number = payload.get("phone_number")
        first_name = payload.get("first_name")
        language = payload.get("language")
        medications = payload.get("medications")
        med_string = construct_medication_string_for_whatsapp(medications)
        med_log_ids = []
        with SessionLocal() as db:
            template = (
                db.query(TwilioWhatsappTemplates)
                .filter(
                    TwilioWhatsappTemplates.language == language,
                    TwilioWhatsappTemplates.template_type == TemplateTypeEnum.medication_reminder.value,
                    TwilioWhatsappTemplates.is_active.is_(True),
                )
                .first()
            )

            if not template:
                raise Exception("No template ID found")
            
            template_id = template.template_id

            for medication in medications:
                med_log = MedicationLog(
                    medication_id = medication['medication_id'],
                    medication_time_id = medication['time_id'],
                    user_id = user_id,
                    status = MedicationStatus.unconfirmed.value
                )
                db.add(med_log)
                db.flush()  # assigns ID without committing
                med_log_ids.append(med_log.id)
            db.commit()
        
        template_dic = {
            1: first_name,
            2: med_string,
            3: ", ".join(str(i) for i in med_log_ids)
        }
        asyncio.run(whatsapp_service.send_message(phone_number, template_dic, template_id))
    
    except Exception as e:
        logger.error(f"error in send_whatsapp_medication_reminder task: {e}")

    




        


