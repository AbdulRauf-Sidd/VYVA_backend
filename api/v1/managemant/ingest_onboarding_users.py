import csv
import io
import re
from sqlalchemy import select
from unittest import result
from fastapi import Form, UploadFile, File, HTTPException
from core.database import get_db
from fastapi import APIRouter, Depends
from schemas.responses import StandardSuccessResponse
from models.onboarding import OnboardingUser
from models.organization import Organization
from scripts.utils import time_to_utc, date_time_to_utc, add_one_day
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from tasks.management_tasks import initiate_onboarding_call
import logging
from pydantic import BaseModel, Field
from typing import Optional
from scripts.utils import construct_onboarding_user_payload

logger = logging.getLogger(__name__)

router = APIRouter()

REQUIRED_COLUMNS = [
    "First Name",
    "Last Name",
    "Country Code",
    "Telephone number",
    "Time Zone",
    "Language",
    "Data Consent",
    "Address",
    "City/State/Province",
    "Postal/Zip Code",
    "Preferred Comm Channels",
    "Caregiver Name",
    "Caregiver Contact Number",
    "Preferred Call Time (24h)",
    "Emergency Alert Number"
]
	
VALID_LANGUAGES = {"english", "german", "spanish", "french", "italian", "turkish", "portuguese", "Dutch", "swedish", "danish", "norwegian", "finnish", "polish", "other"}
VALID_TIMEZONES = {
    "UTC",
    "Europe/Berlin",

    # Europe Mainland (Central Europe Time zone)
    "Europe/Paris",      # France
    "Europe/Rome",       # Italy
    "Europe/Madrid",     # Spain
    "Europe/Vienna",     # Austria
    "Europe/Zurich",     # Switzerland
    "Europe/Amsterdam",  # Netherlands
    "Europe/Brussels",   # Belgium
    "Europe/Stockholm",  # Sweden
    "Europe/Copenhagen", # Denmark
    "Europe/Oslo",       # Norway
    "Europe/Warsaw",     # Poland
    "Europe/Prague",     # Czech Republic
    "Europe/Budapest",   # Hungary
    "Europe/Bratislava", # Slovakia
    "Europe/Luxembourg",

    # Eastern Europe
    "Europe/Helsinki",   # Finland
    "Europe/Riga",       # Latvia
    "Europe/Vilnius",    # Lithuania
    "Europe/Bucharest",  # Romania
    "Europe/Sofia",      # Bulgaria
    "Europe/Athens",     # Greece

    "Europe/London",     # UK (not CET)
    "Europe/Istanbul",   # Türkiye
    "Europe/Lisbon",
    "America/New_York",
    "America/Chicago",
    "America/Denver",
    "America/Los_Angeles",
    "America/Toronto",
    "America/Vancouver",
    "Pacific/Auckland",
    "Australia/Sydney",
    "Asia/Hong_Kong",
    "Asia/Tokyo",
    "Asia/Dubai",
    "Asia/Kolkata",
    "Asia/Singapore"
}

VALID_COMM_METHODS = {"telephone", "app"}
VALID_YES_NO = {"yes", "no"}
VALID_TRUE_FALSE = {"true", "false"}

async def validate_csv(file_content: str, db):
    errors = []
    reader = csv.DictReader(io.StringIO(file_content))

    if reader.fieldnames is None:
        errors.append("CSV has no header row")
        return errors

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
    if missing_cols:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing_cols)}")

    for i, row in enumerate(reader, start=1):
        if i <= 2:
            continue
        # Normalize for simpler validation:
        row_norm = {k.lower().strip(): (v or "").strip() for k, v in row.items()}

        first_name = row_norm.get("first name", "")
        if not first_name:
            errors.append(f"Row {i}: Missing first name.")

        last_name = row_norm.get("last name", "")
        if not last_name:
            errors.append(f"Row {i}: Missing last name.")

        phone = row_norm.get("telephone number", "")
        if not phone:
            errors.append(f"Row {i}: Missing telephone number.")

        country_code = row_norm.get("country code", "")
        if not country_code:
            errors.append(f"Row {i}: Missing country code.")

        full_phone = f"+{country_code}{phone}" if "+" not in country_code else f"{country_code}{phone}"
        phone_pattern = re.compile(r"^\+\d{7,15}$")
        if not phone_pattern.match(full_phone.replace(" ", "").replace("-", "")):
            errors.append(f"Row {i}: Invalid phone number format '{full_phone}'. Must be in E.164 format.")

        timezone = row_norm.get("time zone", "")
        if timezone not in VALID_TIMEZONES:
            errors.append(f"Row {i}: Invalid time zone '{timezone}'. Must be IANA format.")

        lang = row_norm.get("language", "").lower()
        if lang not in VALID_LANGUAGES:
            errors.append(f"Row {i}: Invalid language '{lang}'. Allowed: {', '.join(VALID_LANGUAGES)}")

        consent = row_norm.get("data consent", "").lower()
        if consent not in VALID_TRUE_FALSE:
            errors.append(f"Row {i}: Invalid data consent value '{consent}'. Must be true/false.")

        comm = row_norm.get("preferred comm channels", "").lower()
        if comm not in VALID_COMM_METHODS:
            errors.append(f"Row {i}: Invalid comm method '{comm}'. Must be telephone/app.")

        preferred_time = row_norm.get("preferred call time (24h)", "") or None
        converted_time = None

        try:
            preferred_time_obj = datetime.strptime(preferred_time, "%H:%M").time()
            converted_time = preferred_time_obj.strftime("%H:%M")
        except ValueError:
            converted_time = None

        if not converted_time and preferred_time:
            errors.append(f"Row {i}: Invalid preferred call time '{preferred_time}'. Must be in HH:MM 24-hour format.")

    return errors

async def process_valid_data(file_content, organization, db):
    try:
        
        reader = csv.DictReader(io.StringIO(file_content))
        new_users = []
        agent_id = organization.onboarding_agent_id
        organization_id = organization.id


        for i, row in enumerate(reader, start=1):
            if i <= 2:
                continue
            row_norm = {k.lower().strip(): (v or "").strip() for k, v in row.items()}

            first_name = row_norm.get("first name", "")
            last_name = row_norm.get("last name", "")
            phone_number = row_norm.get("telephone number", "")
            country_code = row_norm.get("country code", "")
            full_phone = f"+{country_code}{phone_number}" if "+" not in country_code else f"{country_code}{phone_number}"
            care_giver_name = row_norm.get("caregiver name", None) or None
            care_giver_contact_number = row_norm.get("caregiver contact number", None) or None
            full_caregiver_phone = f"+{country_code}{care_giver_contact_number}" if care_giver_contact_number and "+" not in country_code else (care_giver_contact_number or None)
            language = row_norm.get("language", "").lower()
            timezone = row_norm.get("time zone", "")  # NO LOWER()
            preferred_communication_channel = row_norm.get("preferred comm channels", "").lower()

            preferred_time = row_norm.get("preferred call time (24h)", "") or None
            address = row_norm.get("address", None)

            utc_dt = None

            # -----------------------------------------
            # Preferred time conversion
            # -----------------------------------------
            if preferred_time:
                # 24-hour format first
                if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", preferred_time):
                    converted_time = preferred_time
                    preferred_time_obj = datetime.strptime(converted_time, "%H:%M").time()

                    #Build full local datetime
                    local_dt = datetime.combine(date.today(), preferred_time_obj, tzinfo=ZoneInfo(timezone))
                    utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
                    final_utc_dt = add_one_day(utc_dt)
            else:
                default_time = datetime.strptime("09:00", "%H:%M").time()

                # Local time 9am tomorrow
                local_dt = datetime.combine(date.today(), default_time, tzinfo=ZoneInfo(timezone))
                local_dt_next_day = add_one_day(local_dt)

                # Convert to UTC
                final_utc_dt = local_dt_next_day.astimezone(ZoneInfo("UTC"))

            city_state_province = row_norm.get('city/state/province', None)
            postal_zip_code = row_norm.get('postal/zip code', None)


            user = OnboardingUser(
                first_name=first_name,
                last_name=last_name,
                phone_number=full_phone,
                language=language,
                preferred_time=final_utc_dt.time() if utc_dt else None,
                timezone=timezone,
                caregiver_name=care_giver_name,
                caregiver_contact_number=full_caregiver_phone,
                preferred_communication_channel=preferred_communication_channel,
                organization_id=organization_id,
                address=address,
                city_state_province=city_state_province,
                postal_zip_code=postal_zip_code,
            )

            db.add(user)
            await db.commit()

            payload = await construct_onboarding_user_payload(user, organization.onboarding_agent_id)

            task_result = initiate_onboarding_call.apply_async(
                args=[payload,],
                eta=final_utc_dt
            )

            logger.info(f"Scheduled onboarding call task {task_result.id} for user {phone_number} at {final_utc_dt} UTC")
            new_users.append(user)

        if new_users:
            await db.commit()

        return True, len(new_users)
    except Exception as e:
        await db.rollback()
        logger.error(f"Error processing onboarding users: {e}")
        return False, 0

@router.post("/ingest-csv", response_model=StandardSuccessResponse)
async def ingest_csv(organization: str = Form(...), file: UploadFile = File(...), db=Depends(get_db)):
    organization = organization.strip()
    result = await db.execute(select(Organization).where(Organization.name == organization))
    exists = result.scalar()
    if not exists:
        raise HTTPException(status_code=400, detail="Organization does not exist.")
    
    content = (await file.read()).decode("utf-8")
    errors = await validate_csv(content, db)
    
    if errors:
        logger.error(f"CSV validation errors: {errors}")
        raise HTTPException(status_code=400, detail=errors)

    success, count = await process_valid_data(content, exists, db)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to process data.")
    
    return {
        'success': True,
        "message": f"Created Onboarding Batch for {count} users.",
    }

class IngestUserRequest(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    country_code: str = Field(..., min_length=1)
    telephone_number: str = Field(..., min_length=1)
    time_zone: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    caregiver_name: Optional[str] = Field(None)
    caregiver_contact_number: Optional[str] = Field(None)
    city_state_province: Optional[str] = Field(None)
    postal_zip_code: Optional[str] = Field(None)
    preferred_call_time: Optional[str] = Field(..., min_length=1)
    
@router.post("/ingest-user", response_model=StandardSuccessResponse)
async def ingest_csv(payload: IngestUserRequest, organization: str, db=Depends(get_db)):
    
    organization = organization.strip()
    print(payload)
    db = await get_db().__anext__()
    result = await db.execute(select(Organization).where(Organization.name == organization))
    exists = result.scalar()
    
    if not exists:
        raise HTTPException(status_code=404, detail="Organization does not exist.")

    full_phone = f"+{payload.country_code}{payload.telephone_number}" if "+" not in payload.country_code else f"{payload.country_code}{payload.telephone_number}"
    phone_pattern = re.compile(r"^\+\d{7,15}$")
    
    if not phone_pattern.match(full_phone.replace(" ", "").replace("-", "")):
        raise HTTPException(status_code=422, detail=f"Invalid phone number format '{full_phone}'. Must be in E.164 format.")
    
    if payload.time_zone not in VALID_TIMEZONES:
        raise HTTPException(status_code=422, detail=f"Invalid time zone '{payload.time_zone}'. Must be IANA format.")  
    
    if not payload.first_name:
        raise HTTPException(status_code=422, detail="Missing first name.")
        
    if not payload.last_name:
        raise HTTPException(status_code=422, detail="Missing last name.")
    
    if not payload.telephone_number:
        raise HTTPException(status_code=422, detail="Missing telephone number.")

    if not payload.country_code:
        raise HTTPException(status_code=422, detail="Missing country code.")
    
    if not payload.language.lower() in VALID_LANGUAGES:
        raise HTTPException(status_code=422, detail=f"Invalid language '{payload.language}'. Allowed: {', '.join(VALID_LANGUAGES)}")
    
    utc_dt = None
    final_utc_dt = None
    if payload.preferred_call_time:
        if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", payload.preferred_call_time):
            converted_time = payload.preferred_call_time
            preferred_time_obj = datetime.strptime(converted_time, "%H:%M").time()

            local_dt = datetime.combine(date.today(), preferred_time_obj, tzinfo=ZoneInfo(payload.time_zone))
            utc_dt = local_dt.astimezone(ZoneInfo("UTC"))
            final_utc_dt = add_one_day(utc_dt)
        else:
            default_time = datetime.strptime("09:00", "%H:%M").time()

            local_dt = datetime.combine(date.today(), default_time, tzinfo=ZoneInfo(payload.time_zone))
            local_dt_next_day = add_one_day(local_dt)

            final_utc_dt = local_dt_next_day.astimezone(ZoneInfo("UTC"))

    user = OnboardingUser(
                first_name=payload.first_name,
                last_name=payload.last_name,
                phone_number=payload.telephone_number,
                timezone=payload.time_zone,
                organization_id=exists.id,
                language=payload.language.lower(),
                caregiver_name=payload.caregiver_name,
                caregiver_contact_number=payload.caregiver_contact_number,
                city_state_province=payload.city_state_province,
                postal_zip_code=payload.postal_zip_code,
                preferred_time=final_utc_dt,
            )
    
    task_payload = await construct_onboarding_user_payload(user, exists.onboarding_agent_id)
    
    task_result = initiate_onboarding_call.apply_async(
                args=[task_payload,],
                eta=final_utc_dt
            )
    
    db.add(user)
    await db.commit()
    
    return {
        'success': True,
        "message": f"Created Onboarding User {payload.first_name} {payload.last_name}.",
    }
