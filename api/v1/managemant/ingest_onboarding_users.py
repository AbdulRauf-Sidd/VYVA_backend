import csv
import io
import re
from select import select
from unittest import result
from fastapi import UploadFile, File, HTTPException
from core.database import get_db
from fastapi import APIRouter, Depends
from schemas.responses import StandardSuccessResponse
from models.user import User
from models.organization import Organization

router = APIRouter()

REQUIRED_COLUMNS = [
    "First Name*",
    "Last Name*",
    "Phone Number*",
    "Language*",
    "Time Zone*",
    "Reporting: Email (Yes/No)",
    "Reporting: WhatsApp (Yes/No)",
]

VALID_LANGUAGES = {"en", "de", "es"}
VALID_TIMEZONES = {"utc", "cet", "est"}
VALID_COMM_METHODS = {"phone", "email"}
VALID_YES_NO = {"yes", "no"}

def validate_csv(file_content: str):
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
        if phone and not re.match(r"^\+\d{6,15}$", phone.strip()):
            errors.append(f"Row {i}: Invalid phone number '{phone}'. Expected format: + followed by digits.")

        email = row.get("Email", "")
        if email and not re.match(r"^[^@]+@[^@]+\.[^@]+$", email.strip()):
            errors.append(f"Row {i}: Invalid email '{email}'.")

        lang = row.get("Language*", "").lower()
        if lang and lang not in VALID_LANGUAGES:
            errors.append(f"Row {i}: Invalid language '{lang}'. Must be one of {VALID_LANGUAGES}.")

        time_pref = row.get("Preferred Time", "")
        if time_pref and not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", time_pref.strip()):
            errors.append(f"Row {i}: Invalid Preferred Time '{time_pref}'. Must be in HH:MM 24-hour format.")

        tz = row.get("Time Zone*", "").lower()
        if tz and tz not in VALID_TIMEZONES:
            errors.append(f"Row {i}: Invalid Time Zone '{tz}'. Must be one of {VALID_TIMEZONES}.")

        comm = row.get("Preferred Communication Method", "")
        if comm and comm.lower() not in VALID_COMM_METHODS:
            errors.append(f"Row {i}: Invalid Communication Method '{comm}'. Must be one of {VALID_COMM_METHODS}.")

        email_report = row.get("Reporting: Email (Yes/No)", "").lower()
        if email_report not in VALID_YES_NO:
            errors.append(f"Row {i}: Invalid 'Reporting: Email (Yes/No)' value '{email_report}'. Must be Yes or No.")

        whatsapp_report = row.get("Reporting: WhatsApp (Yes/No)", "").lower()
        if whatsapp_report not in VALID_YES_NO:
            errors.append(f"Row {i}: Invalid 'Reporting: WhatsApp (Yes/No)' value '{whatsapp_report}'. Must be Yes or No.")

    return errors

def process_valid_data(file_content: str):
    
    return {"message": "File validated and processed successfully."}

@router.post("/admin/ingest-csv", response_model=StandardSuccessResponse)
async def ingest_csv(organization: str, file: UploadFile = File(...), db=Depends(get_db)):
    organization = organization.strip()
    result = await db.execute(select(Organization).where(Organization.name == organization))
    exists = result.scalar()
    if not exists:
        raise HTTPException(status_code=400, detail="Organization does not exist.")
    content = (await file.read()).decode("utf-8")
    errors = validate_csv(content)
    
    if errors:
        raise HTTPException(status_code=400, detail=errors)
    
    success = process_valid_data(content)
