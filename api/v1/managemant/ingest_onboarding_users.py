import csv
import io
import re
from sqlalchemy import select
from unittest import result
from fastapi import UploadFile, File, HTTPException
from core.database import get_db
from fastapi import APIRouter, Depends
from schemas.responses import StandardSuccessResponse
from models.onboarding_user import OnboardingUser
from models.organization import Organization
from scripts.utils import time_to_utc, date_time_to_utc, add_one_day
from datetime import datetime, date
from models.user import User
from zoneinfo import ZoneInfo
from tasks.management_tasks import initiate_onboarding_call

router = APIRouter()

REQUIRED_COLUMNS = [
    "First Name*",
    "Last Name*",
    "Phone Number*",
    "Email"
    "Preferred Time of call (if blank, agent will call next day at 9am CET)"
    "Language*",
    "Time Zone*",
    "Preferred Communication Method",
    "Reporting: WhatsApp (Yes/No)",
    "Landline",
]

VALID_LANGUAGES = {"english", "german", "spanish"}
VALID_TIMEZONES = {"utc", "cet", "est"}
VALID_COMM_METHODS = {"phone", "Web App"}
VALID_YES_NO = {"yes", "no"}

async def validate_csv(file_content: str, db):
    errors = []
    reader = csv.DictReader(io.StringIO(file_content))

    missing_cols = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
    if missing_cols:
        raise HTTPException(status_code=400, detail=f"Missing required columns: {', '.join(missing_cols)}")

    for i, row in enumerate(reader, start=2):  
        for col in REQUIRED_COLUMNS:
            if not row.get(col) or row[col].strip() == "":
                errors.append(f"Row {i}: '{col}' is required.")

        phone = row.get("Phone Number*", "")
        if phone and not phone.startswith("+"):
            phone = "+" + phone
        if phone and not re.match(r"^\+\d{6,15}$", phone.strip()):
            errors.append(f"Row {i}: Invalid phone number '{phone}'. Expected format: + followed by digits.")

        landline = row.get("Landline", "")
        if landline and not landline.startswith("+"):
            landline = "+" + landline
        if landline and not re.match(r"^\+\d{6,15}$", landline.strip()):
            errors.append(f"Row {i}: Invalid landline number '{landline}'. Expected format: + followed by digits.")

        if phone:
            result = await db.execute(select(User).where(User.phone_number == phone.strip()))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                errors.append(f"Row {i}: Phone number '{phone}' already exists.")

        if landline:
            result = await db.execute(select(User).where(User.land_line == landline.strip()))
            existing_user = result.scalar_one_or_none()
            if existing_user:
                errors.append(f"Row {i}: Landline '{landline}' already exists.")

        email = row.get("Email", "")
        if email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", email.strip()):
            errors.append(f"Row {i}: Invalid email '{email}'.")

        lang = row.get("Language*", "").lower()
        if lang and lang not in VALID_LANGUAGES:
            errors.append(f"Row {i}: Invalid language '{lang}'. Must be one of {VALID_LANGUAGES}.")

        time_pref = row.get("Preferred Time of call (if blank, agent will call next day at 9am CET)", "")
        if time_pref:
            if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time_pref):
                pass
            else:
                try:
                    dt = datetime.strptime(time_pref, "%I:%M %p")
                    dt.strftime("%H:%M")
                except ValueError:
                    errors.append(
                        f"Row {i}: Invalid Preferred Time '{time_pref}'. Must be HH:MM 24-hour or hh:mm AM/PM format."
                    )

        tz = row.get("Time Zone*", "").lower()
        if tz and tz not in VALID_TIMEZONES:
            errors.append(f"Row {i}: Invalid Time Zone '{tz}'. Must be one of {VALID_TIMEZONES}.")

        comm = row.get("Preferred Communication Method", "")
        if comm and comm.lower() not in VALID_COMM_METHODS:
            errors.append(f"Row {i}: Invalid Communication Method '{comm}'. Must be one of {VALID_COMM_METHODS}.")

        # email_report = row.get("Reporting: Email (Yes/No)", "").lower()
        # if email_report not in VALID_YES_NO:
        #     errors.append(f"Row {i}: Invalid 'Reporting: Email (Yes/No)' value '{email_report}'. Must be Yes or No.")

        whatsapp_report = row.get("Reporting: WhatsApp (Yes/No)", "").lower()
        if whatsapp_report not in VALID_YES_NO:
            errors.append(f"Row {i}: Invalid 'Reporting: WhatsApp (Yes/No)' value '{whatsapp_report}'. Must be Yes or No.")

    return errors

async def process_valid_data(file_content, organization_id, db):
    try:

        reader = csv.DictReader(io.StringIO(file_content))
        org = result.scalar_one_or_none()
        new_users = []

        for i, row in enumerate(reader, start=2):
            first_name=row["First Name*"].strip()
            last_name=row["Last Name*"].strip()
            phone_number=row["Phone Number*"].strip()
            land_line=row.get("Landline", "").strip() or None
            email=row.get("Email", "").strip() or None
            language=row["Language*"].strip().lower()
            preferred_time=row.get("Preferred Time of call (if blank, agent will call next day at 9am CET)", "").strip() or None
            timezone=row["Time Zone*"].strip().lower()
            whatsapp_reports=row["Reporting: WhatsApp (Yes/No)"].strip().lower()

            converted_time = None

            if preferred_time:
                # Try 24-hour format first
                if re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", preferred_time):
                    converted_time = preferred_time
                else:
                    # Try 12-hour format (e.g., 02:30 PM)
                    try:
                        dt = datetime.strptime(preferred_time, "%I:%M %p")
                        converted_time = dt.strftime("%H:%M")  # convert to 24-hour
                    except ValueError:
                        pass

            if converted_time:
                preferred_time = datetime.strptime(converted_time, "%H:%M").time()
                utc_time_object = time_to_utc(preferred_time, timezone)
                utc_dt = datetime.combine(date.today(), utc_time_object, tzinfo=ZoneInfo("UTC"))
                final_utc_dt = add_one_day(utc_dt)
            else:
                preferred_time = datetime.strptime('09:00', "%H:%M").time()
                utc_time_object = time_to_utc(preferred_time, 'cet')
                utc_dt = datetime.combine(date.today(), utc_time_object, tzinfo=ZoneInfo("UTC"))
                final_utc_dt = add_one_day(utc_dt)


            preferred_communication_channel=row.get("Preferred Communication Method", "").strip().lower() or None
            # email_reports=row["Reporting: Email (Yes/No)"].strip().lower()
            # whatsapp_reports=row["Reporting: WhatsApp (Yes/No)"].strip().lower()
            # email_reports = True if email_reports == "yes" else False
            whatsapp_reports = True if whatsapp_reports == "yes" else False

            user = OnboardingUser(
                first_name=first_name,
                last_name=last_name,
                phone_number=phone_number,
                email=email,
                language=language,
                preferred_time=preferred_time,
                timezone=timezone,
                preferred_communication_channel=preferred_communication_channel,
                land_line=land_line,
                whatsapp_reports=whatsapp_reports,
                organization_id=organization_id,
            )

            task_result = initiate_onboarding_call.apply_async(
                args=[user],
                eta=final_utc_dt
            )
            print(f"Scheduled onboarding call task {task_result.id} for user {phone_number} at {final_utc_dt} UTC")
            new_users.append(user)

        if new_users:
            db.add_all(new_users)
            await db.commit()

        return True, len(new_users)
    except Exception as e:
        await db.rollback()
        print(e)
        return False, 0

@router.post("/ingest-csv", response_model=StandardSuccessResponse)
async def ingest_csv(organization: str = 'Red Cross', file: UploadFile = File(...), db=Depends(get_db)):
    organization = organization.strip()
    result = await db.execute(select(Organization).where(Organization.name == organization))
    exists = result.scalar()
    if not exists:
        raise HTTPException(status_code=400, detail="Organization does not exist.")
    
    content = (await file.read()).decode("utf-8")
    errors = await validate_csv(content, db)
    
    if errors:
        print(errors)
        print('error_messages', errors)
        raise HTTPException(status_code=400, detail=errors)

    success, count = await process_valid_data(content, exists.id, db)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to process data.")
    
    return {
        'success': True,
        "message": f"Created Onboarding Batch for {count} users.",
    }
