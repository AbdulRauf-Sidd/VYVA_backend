from fastapi import APIRouter, Depends, HTTPException, status, Body, Response
from core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User, Caretaker
from models.onboarding import OnboardingUser
from datetime import datetime, timedelta
from sqlalchemy.sql import func
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from core.database import get_db
# from services.email_service import email_service
from services.sms_service import sms_service
import logging
from schemas.onboarding_user import OnboardingRequestBody
from scripts.utils import get_or_create_caregiver, construct_mem0_memory_onboarding, get_iso_language
from schemas.medication import BulkMedicationSchema
from repositories.medication import MedicationRepository
from services.medication import MedicationService
from models.user_check_ins import UserCheckin, ScheduledSession, CheckInType
from models.authentication import CaretakerTempToken, UserTempToken
# from services.whatsapp_service import whatsapp_service
from services.mem0 import add_conversation
from datetime import timezone
from typing import Optional
from celery.result import AsyncResult
from scripts.onboarding_utils import construct_onboarding_message_for_caretaker, construct_onboarding_message_for_user


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
        preferences = data.get("preferences", [])
        mobility = data.get("mobility", [])
        city = record.city_state_province if record.city_state_province else ""
        postal_code = record.postal_zip_code if record.postal_zip_code else ""
        address = record.address if record.address else address

        caregiver_phone = record.caregiver_contact_number if record.caregiver_contact_number else caretaker_phone
        

        if caregiver_phone:
            caregiver, created = await get_or_create_caregiver(db, caregiver_phone, caretaker_name)
        else:
            caregiver = None

        language = record.language.lower() if record.language else "english"

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
            preferred_consultation_language=language,
            health_conditions=", ".join(health_conditions) if health_conditions else None,
            mobility=", ".join(mobility) if mobility else None,
            caretaker_id=caregiver.id if caregiver_phone else None,
            caretaker_consent=caretaker_consent,
            caretaker=caregiver if caregiver_phone else None,
            preferred_reminder_channel=payload.preferred_reminder_channel,
            preferred_reports_channel=payload.preferred_reports_channel,
            timezone=record.timezone,
            organization_id=record.organization_id,
        )

        db.add(user)
        await db.flush()
        await db.refresh(user)

        record.onboarding_status = True
        record.onboarded_at = datetime.now(timezone.utc)
        db.add(record)        

        wants_brain_coach = brain_coach.get("wants_brain_coach_sessions", False)
        frequency_in_days = brain_coach.get("frequency_in_days", None)
        if wants_brain_coach:
            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.brain_coach.value,
                check_in_frequency_days=frequency_in_days if frequency_in_days else 7,
            )
            db.add(check_in)

        wants_daily_check_ins = check_in_details.get("wants_check_ins", False)
        check_in_frequency = check_in_details.get("frequency_in_days", None)
        if wants_daily_check_ins:
            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.check_up_call.value,
                check_in_frequency_days=check_in_frequency if check_in_frequency else 7,
            )
            db.add(check_in)

        if medication_details:
            medication_request = BulkMedicationSchema(
                medication_details=medication_details,
                user_id=user.id,
            )
            medication_repo = MedicationRepository(db)
            medication_service = MedicationService(medication_repo)
            await medication_service.process_bulk_medication_request(medication_request)

        temp_token = UserTempToken(
            user_id=user.id,
            expires_at=datetime.now() + timedelta(hours=96),
            used=False
        )

        temp_token_caregiver = None

        if caregiver:
            temp_token_caregiver = CaretakerTempToken(
                caretaker_id=caregiver.id,
                expires_at=datetime.now() + timedelta(hours=96),
                used=False
            )
            db.add(temp_token_caregiver)

        db.add(temp_token)
        await db.commit()

        mem0_payload = []

        if mobility:
            mem0_payload += construct_mem0_memory_onboarding(", ".join(mobility), "mobility")
            await add_conversation(user.id, mem0_payload)
        if health_conditions:
            mem0_payload += construct_mem0_memory_onboarding(", ".join(health_conditions), "health_conditions")
            await add_conversation(user.id, mem0_payload)
        if preferences:
            mem0_payload += construct_mem0_memory_onboarding(", ".join(preferences), "preferences")
            await add_conversation(user.id, mem0_payload)
        
        # Send WhatsApp message with onboarding link
        onboarding_link = f"https://{record.organization.sub_domain}.vyva.io/verify?token={temp_token.token}"
        temmplate_data = {
            "link": onboarding_link
        }

        iso_language = get_iso_language(language)
        user_message = construct_onboarding_message_for_user(iso_language, onboarding_link)
        await sms_service.send_sms(user.phone_number, user_message)
        
        # await whatsapp_service.send_onboarding_message(user.phone_number, temmplate_data)
        

        
        if temp_token_caregiver:
            caregiver_onboarding_link = f"https://care-{record.organization.sub_domain}.vyva.io/senior-verification?token={temp_token_caregiver.token}"
            caregiver_message = construct_onboarding_message_for_caretaker(iso_language, caregiver_onboarding_link)
            await sms_service.send_sms(user.phone_number, caregiver_message)
            # temmplate_data = {
            #     "caregiver_magic_link": caregiver_onboarding_link
            # }

            # await whatsapp_service.send_onboarding_message(caregiver.phone_number, temmplate_data, template_id=settings.TWILIO_WHATSAPP_CARETAKER_ONBOARDING_TEMPLATE_SID)

        return {
            "status": "success",
            "message": "Payload processed",
            "received": payload.model_dump()
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error processing payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

    
@router.get(
    "/onboarding-users",
    status_code=status.HTTP_200_OK,
    summary="Get all onboarding users",
    description="Retrieve a list of all onboarding users"
)
async def get_onboarding_users(
    db: AsyncSession = Depends(get_db), 
    organization_id: int = None, 
    limit: int = 5, 
    offset: int = 0, 
    status: Optional[str] = None, 
    language: Optional[str] = None, 
    caretaker: Optional[bool] = None, 
    q: Optional[str] = None
):
    try:
        query = select(OnboardingUser)

        if organization_id:
            query = query.where(OnboardingUser.organization_id == organization_id)
        if status:
            if status.lower() == "completed":
                query = query.where(OnboardingUser.onboarding_status == True)
            elif status.lower() == "pending":
                query = query.where((OnboardingUser.onboarding_status == False) & (OnboardingUser.call_attempts < 3))
            elif status.lower() == "failed":
                query = query.where((OnboardingUser.onboarding_status == False) & (OnboardingUser.call_attempts >= 3))
        if language:
            query = query.where(func.lower(OnboardingUser.language) == language.lower())
        if caretaker == True:
            query = query.where((OnboardingUser.caregiver_name.isnot(None)) & (OnboardingUser.caregiver_contact_number.isnot(None)))
        elif caretaker == False:
            query = query.where(OnboardingUser.caregiver_name.is_(None))
        if q:
            search = f"%{q}%"
            query = query.where(
                OnboardingUser.first_name.ilike(search) |
                OnboardingUser.last_name.ilike(search)
            )

        query = query.limit(limit).offset(offset)

        result = await db.execute(query)
        records = result.scalars().all()
        return records
    except Exception as e:
        logger.error(f"Error retrieving onboarding users: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")
       

@router.delete(
    "/onboarding-users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete onboarding user by ID",
    description="Delete an onboarding user by their ID and revoke any scheduled tasks"
)
async def delete_onboarding_user_by_id(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    try:
        # Use db.get for safe ORM instance
        record = await db.get(OnboardingUser, user_id)
        if not record:
            raise HTTPException(status_code=404, detail="User not found")

        # Revoke Celery task if present
        if record.onboarding_call_task_id:
            try:
                task = AsyncResult(record.onboarding_call_task_id)
                task.revoke(terminate=True)
                logger.info(f"Revoked Celery task {record.onboarding_call_task_id}")
            except Exception as task_e:
                logger.warning(f"Failed to revoke Celery task {record.onboarding_call_task_id}: {task_e}")

        # Delete the user
        await db.delete(record)
        await db.commit()

        return Response(status_code=204)

    except HTTPException:
        # Let FastAPI handle it (404)
        raise
    except Exception as e:
        logger.exception(f"Error deleting onboarding user {user_id}")
        raise HTTPException(status_code=500, detail="Internal server error")