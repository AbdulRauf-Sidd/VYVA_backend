from datetime import datetime, date, time, timedelta
import random
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from models.brain_coach import BrainCoachResponses
from models.user import Caretaker, User
# from models.organization import TwilioWhatsappTemplates, TemplateTypeEnum
# from core.database import SessionLocal
# from sqlalchemy.orm import selectinload
# from services.whatsapp_service import whatsapp_service
import logging

logger = logging.getLogger(__name__)

TZ_MAP = {
    "cet": "Europe/Berlin",
    "est": "America/New_York",
    "utc": "UTC",
}

LANGUAGE_MAP = {
    "english": "en",
    "spanish": "es",
    "german": "de",
    "french": "fr",
}

MEDICATION_MESSAGES_MAP = {
      "english": {
        "taken": [
          "That’s great. Well done taking your medication today.",
          "Good job taking your medication.",
          "Thank you for taking your medication.",
          "Excellent. You are taking good care of your health.",
          "Glad to hear it. Every dose matters."
        ],
        "missed": [
          "That’s okay. Please try to take it when you can.",
          "No problem. You can still take it if it is not too late.",
          "Thank you for letting me know. We will try again next time.",
          "That is alright. Let us stay on track together.",
          "No worries. Tomorrow is another chance."
        ]
      },
    
      "spanish": {
        "taken": [
          "Excelente. Ha hecho muy bien en tomar su medicamento hoy.",
          "Buen trabajo tomando su medicamento.",
          "Gracias por tomar su medicamento.",
          "Excelente. Está cuidando bien su salud.",
          "Me alegra saberlo. Cada dosis es importante."
        ],
        "missed": [
          "Está bien. Por favor tómelo cuando pueda.",
          "No hay problema. Aún puede tomarlo si no es demasiado tarde.",
          "Gracias por avisar. Lo intentaremos de nuevo la próxima vez.",
          "No se preocupe. Seguiremos manteniendo el control.",
          "No pasa nada. Mañana es una nueva oportunidad."
        ]
      },
    
      "german": {
        "taken": [
          "Sehr gut. Sie haben Ihr Medikament heute richtig eingenommen.",
          "Gut gemacht beim Einnehmen Ihres Medikaments.",
          "Vielen Dank, dass Sie Ihr Medikament eingenommen haben.",
          "Ausgezeichnet. Sie kümmern sich gut um Ihre Gesundheit.",
          "Das freut mich zu hören. Jede Dosis ist wichtig."
        ],
        "missed": [
          "Das ist in Ordnung. Bitte nehmen Sie es ein, wenn Sie können.",
          "Kein Problem. Sie können es noch einnehmen, wenn es nicht zu spät ist.",
          "Danke für die Rückmeldung. Beim nächsten Mal klappt es wieder.",
          "Alles gut. Wir bleiben gemeinsam dran.",
          "Keine Sorge. Morgen ist eine neue Gelegenheit."
        ]
      }
    }

def date_time_to_utc(dt: datetime, tz_name: str | None = None) -> datetime:
    if dt.tzinfo is None:
        if tz_name:
            dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(ZoneInfo("UTC"))


def time_to_utc(preferred_time: datetime, tz_abbr: str) -> time:
    # local_time = datetime.strptime(preferred_time, "%H:%M").time()
    tz_name = TZ_MAP.get(tz_abbr.lower(), "UTC")
    today = date.today()
    local_dt = datetime.combine(today, preferred_time, tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(ZoneInfo("UTC")).time()

def add_one_day(dt: datetime) -> datetime:
    return dt + timedelta(days=1)


async def get_or_create_caregiver(db: AsyncSession, phone: str, name: str):

    result = await db.execute(
        select(Caretaker).where(Caretaker.phone_number == phone)
    )
    caregiver = result.scalar_one_or_none()

    if caregiver:
        return caregiver, False

    # Create a new one
    caregiver = Caretaker(phone_number=phone, name=name)
    db.add(caregiver)
    await db.flush()
    return caregiver, True


async def construct_onboarding_user_payload(user, agent_id) -> dict:
    if user.address or user.city_state_province or user.postal_zip_code:
        combined_address = f"{user.address}, {user.city_state_province}, {user.postal_zip_code}"
    else:
        combined_address = "not available"

    payload = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "language": user.language,
        'user_id': user.id,
        "agent_id": agent_id,
        "address": combined_address,
        "user_type": user.preferred_communication_channel,
        "caregiver_name": user.caregiver_name,
        "caregiver_contact_number": user.caregiver_contact_number,
        
    }
    return payload


def construct_mem0_memory_onboarding(message, message_type):
    if message_type == "mobility":
        return [
            {"role": "system", "content": "Do you have need any assistance moving around, or are you fully independant?"},
            {"role": "user", "content": message},
        ]
    elif message_type == "health_conditions":
        return [
            {"role": "system", "content": "Do you have any health conditions we should be aware of?"},
            {"role": "user", "content": message},
        ]
    elif message_type == "preferences":
        return [
            {"role": "system", "content": "What is your preferred communication channel?"},
            {"role": "user", "content": message},
        ]
    else:
        return [
            {"role": "system", "content": "Do you have any other information you'd like to share?"},
            {"role": "user", "content": message},
        ]
    

def generate_medication_whatsapp_response_message(language, taken: bool) -> str:
    lang_messages = MEDICATION_MESSAGES_MAP.get(language.lower(), MEDICATION_MESSAGES_MAP["english"])
    if taken:
        return random.choice(lang_messages["taken"])
    else:
        return random.choice(lang_messages["missed"])
    

def calculate_streak(dates: list[date]) -> int:
    if not dates:
        return 0

    today = date.today()
    dates_set = set(dates)

    # Must have activity today or yesterday
    if today not in dates_set and (today - timedelta(days=1)) not in dates_set:
        return 0

    streak = 0
    check_day = today

    # If no session today, start from yesterday
    if check_day not in dates_set:
        check_day = today - timedelta(days=1)

    while check_day in dates_set:
        streak += 1
        check_day -= timedelta(days=1)

    return streak


def get_zoneinfo_safe(tz_name: str | None) -> ZoneInfo:
    """
    Return ZoneInfo or fallback to UTC if invalid/null.
    """
    try:
        if not tz_name:
            logger.warning("No timezone provided, defaulting to UTC.")
            return ZoneInfo("UTC")
        
        return ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        logger.warning(f"Invalid timezone name: {tz_name}, defaulting to UTC.")
        return ZoneInfo("UTC")


def convert_to_utc_datetime(tz_name: str, date: date | None = None, time: time | None = None, dt: datetime | None = None, normalize_seconds: bool = True) -> datetime:
    """
    Convert a local date+time OR datetime into UTC.

    Rules:
    - If dt is provided → use it
    - Else require both d and t
    - If dt is naive → attach tz_name
    - If dt already has tz → convert from it
    - Raises ValueError if insufficient inputs
    """

    try:
        tz = get_zoneinfo_safe(tz_name)

        # --- choose source datetime ---
        if dt is not None:
            local_dt = dt
        elif date is not None and time is not None:
            local_dt = datetime.combine(date, time)
        else:
            raise ValueError("Provide either dt OR both date and time")

        local_dt = local_dt.replace(tzinfo=tz)

        # --- convert to UTC ---
        dt_utc = local_dt.astimezone(ZoneInfo("UTC"))

        if normalize_seconds:
            dt_utc = dt_utc.replace(second=0, microsecond=0)

        return dt_utc
    except Exception as e:
        logger.error(f"Error in to_utc_datetime: {e}")
        return None
