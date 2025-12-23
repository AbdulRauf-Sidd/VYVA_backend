from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User
from models.onboarding import OnboardingUser
from datetime import datetime, timedelta
from sqlalchemy.sql import func
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.database import get_db
from services.email_service import email_service
from services.sms_service import sms_service
import logging
from schemas.onboarding_user import OnboardingRequestBody
from scripts.utils import get_or_create_caregiver
from schemas.medication import BulkMedicationSchema
from repositories.medication import MedicationRepository
from services.medication import MedicationService
from models.user_check_ins import UserCheckin, ScheduledSession, CheckInType
from models.authentication import UserTempToken

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new onboarding user",
    description="Create a new onboarding user with the provided details"
)
async def onboard_user(
    payload: OnboardingRequestBody = Body(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        data = payload.model_dump()
        user_id = data["user_id"]
        result = await db.execute(
            select(OnboardingUser)
            .options(selectinload(OnboardingUser.organization))
            .where(OnboardingUser.id == user_id)
        )
        record = result.scalar_one()
        if not record:
            raise HTTPException(status_code=404, detail="User not found") 
        
        phone_number = record.phone_number
        caretaker_phone = data.get("caretaker_phone", None)
        caretaker_name = data.get("caretaker_name", None)
        address = data["address"]
        medication_details = data.get("medication_details", [])
        check_in_details = data.get("check_in_details", {})
        brain_coach = data.get("brain_coach", {})
        caretaker_consent = data.get("caretaker_consent", False)
        health_conditions = data.get("health_conditions", [])
        mobility = data.get("mobility", [])
        city = record.city_state_province if record.city_state_province else ""
        postal_code = record.postal_zip_code if record.postal_zip_code else ""
        address = record.address if record.address else address

        caregiver_phone = record.caregiver_contact_number if record.caregiver_contact_number else caretaker_phone
        

        if caregiver_phone:
            caregiver, created = await get_or_create_caregiver(db, caregiver_phone, caretaker_name)

        user = User(
            first_name=record.first_name,
            last_name=record.last_name,
            phone_number=phone_number,
            emergency_contact_phone=caregiver_phone,
            emergency_contact_name=record.caregiver_name if record.caregiver_name else caretaker_name,
            address=address,
            city=city,
            postal_code=postal_code,
            preferred_communication_channel=record.preferred_communication_channel,
            preferred_consultation_language=record.language.title(),
            health_conditions=", ".join(health_conditions) if health_conditions else None,
            mobility=", ".join(mobility) if mobility else None,
            caretaker_id=caregiver.id if caregiver_phone else None,
            caretaker_consent=caretaker_consent,
            caretaker=caregiver if caregiver_phone else None,
        )

        db.add(user)
        await db.flush()
        await db.refresh(user)

        record.onboarding_status = True
        record.onboarded_at = datetime.now()
        db.add(record)        

        wants_brain_coach = brain_coach.get("wants_brain_coach_sessions", False)
        frequency_in_days = brain_coach.get("frequency_in_days", None)
        if wants_brain_coach:
            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.BRAIN_COACH,
                check_in_frequency_days=frequency_in_days if frequency_in_days else 7,
            )
            db.add(check_in)

        wants_daily_check_ins = check_in_details.get("wants_check_ins", False)
        check_in_frequency = check_in_details.get("frequency_in_days", None)
        if wants_daily_check_ins:
            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.CHECK_UP_CALL,
                check_in_frequency_days=check_in_frequency if check_in_frequency else 7,
            )
            db.add(check_in)

        if medication_details:
            print('medication_details', medication_details)
            medication_request = BulkMedicationSchema(
                medication_details=medication_details,
                user_id=user.id,
            )
            medication_repo = MedicationRepository(db)
            medication_service = MedicationService(medication_repo)
            await medication_service.process_bulk_medication_request(medication_request)

        temp_token = UserTempToken(
            user_id=user.id,
            expires_at=datetime.now() + timedelta(minutes=15),
            used=False
        )
        db.add(temp_token)
        await db.commit()

        await sms_service.send_magic_link(user.phone_number, temp_token.token, record.organization.sub_domain)

        return {
            "status": "success",
            "message": "Payload processed",
            "received": payload.model_dump()
        }
    except Exception as e:
        logger.error(f"Error processing payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    