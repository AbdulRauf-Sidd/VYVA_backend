from core.database import SessionLocal
from celery_app import celery_app
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
from models.medication import Medication, MedicationTime, MedicationStatus
from models.organization import OrganizationAgents, AgentTypeEnum
from sqlalchemy import or_, select
from models.eleven_labs_sessions import ElevenLabsSessions
from scripts.utils import notify_caretaker_on_missed_meds
from tasks.utils import schedule_celery_task_for_call_status_check, schedule_reminder_message, update_medication_status

# from scripts.utils import construct_onboarding_user_payload

from twilio.rest import Client
from core.config import settings

logger = logging.getLogger(__name__)

@celery_app.task(name="notify_caregiver_on_missed_medication_task")
def notify_caregiver_on_missed_medication_task(user_id: int):
    notify_caretaker_on_missed_meds(user_id)