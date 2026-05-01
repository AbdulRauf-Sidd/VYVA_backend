from fastapi import APIRouter, Depends, HTTPException, status, Body, Response, Query
from sqlalchemy.ext.asyncio import AsyncSession
from models.medication import Medication, MedicationTime
from models.user import User
from models.onboarding import OnboardingUser
from datetime import datetime, timedelta, time
from sqlalchemy.sql import func
from sqlalchemy import select, union_all, literal
from sqlalchemy.orm import selectinload
from core.database import get_db
import logging
from schemas.onboarding_user import OnboardingRequestBody, OnboardingRequestBodyRedCross, OnboardingRequestBodyZamora
from scripts.medication_utils import construct_days_array_from_string
from scripts.utils import get_or_create_caregiver, construct_mem0_memory_onboarding, date_now_in_timezone, convert_to_utc_datetime, parse_time_string
from models.user_check_ins import UserCheckin, CheckInType
from models.organization import Organization
from services.mem0 import add_conversation
from datetime import timezone as timezone_obj
from typing import Optional
from celery.result import AsyncResult
from scripts.onboarding_utils import construct_onboarding_user_payload, send_onboarding_sms
from celery_app import celery_app
from tasks.onboarding_tasks import set_location_coordinates

logger = logging.getLogger(__name__)

router = APIRouter()


def _parse_positive_int(value: Optional[str], field_name: str, default: Optional[int] = None) -> int:
    if value is None:
        if default is not None:
            return default
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail=f"{field_name} must be an integer")
    if parsed <= 0:
        raise HTTPException(status_code=400, detail=f"{field_name} must be greater than 0")
    return parsed

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
        
        if data.get("call_back_date_time"):
            callback_date = data["call_back_date_time"].date()
            user_today = date_now_in_timezone(record.timezone)
            dt_utc = convert_to_utc_datetime(tz_name=record.timezone, dt=data["call_back_date_time"])
            if callback_date == user_today:
                onboarding_payload = construct_onboarding_user_payload(record, record.organization.onboarding_agent_id)

                task = celery_app.send_task(
                    "initiate_onboarding_call",
                    args=[onboarding_payload,],
                    eta=dt_utc
                )
                
                record.onboarding_call_scheduled = True
                record.onboarding_call_task_id = task.id
                logger.info('celery call back task scheduled for user {record.first_name}, {task.id}')
            record.call_back_date_time = dt_utc
            db.add(record)
            await db.commit()
            logger.info('call back time added to user')
            return
        
        # --- check consent ---
        record.consent_given = payload.consent_given
        if not payload.consent_given:
            db.add(record)
            await db.commit()
            return
        
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
        preferred_reports_channel = payload.preferred_reports_channel
        if preferred_reports_channel not in ['whatsapp', 'email']:
            preferred_reports_channel = 'whatsapp'

        caregiver_phone = record.caregiver_contact_number if record.caregiver_contact_number else caretaker_phone

        if caregiver_phone:
            caregiver, created = await get_or_create_caregiver(db, caregiver_phone, caretaker_name)
        else:
            caregiver = None

        language = record.language.lower() if record.language else "spanish"

        user = User(
            first_name=record.first_name,
            last_name=record.last_name,
            phone_number=phone_number,
            street=address,
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
            organization_id=record.organization_id
        )

        db.add(user)
        await db.flush()
        await db.refresh(user)

        record.onboarding_status = True
        record.onboarded_at = datetime.now(timezone_obj.utc)
        db.add(record)        

        wants_brain_coach = brain_coach.get("wants_brain_coach_sessions", False)
        frequency_in_days = brain_coach.get("frequency_in_days", None)
        time_of_day = brain_coach.get("time_of_day", None)
        if wants_brain_coach:
            if not time_of_day:
                time_of_day = "12:00" #defaulting to 12 PM if no time provided

            time_obj = parse_time_string(time_of_day)
            # utc_time = convert_local_time_to_utc_time(time_obj, user.timezone)
            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.brain_coach.value,
                check_in_frequency_days=frequency_in_days if frequency_in_days else 7,
                check_in_time=time_obj
            )
            db.add(check_in)

        wants_daily_check_ins = check_in_details.get("wants_check_ins", False)
        check_in_frequency = check_in_details.get("frequency_in_days", None)
        time_of_day = check_in_details.get("time_of_day", None)
        if wants_daily_check_ins:
            if not time_of_day:
                time_of_day = "09:00" #defaulting to 9 AM if no time provided

            time_obj = parse_time_string(time_of_day)
            # utc_time = convert_local_time_to_utc_time(time_obj, user.timezone)
            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.check_up_call.value,
                check_in_frequency_days=check_in_frequency if check_in_frequency else 7,
                check_in_time=time_obj
            )
            db.add(check_in)

        if medication_details:
            for med_input in medication_details:
                # Start date
                if med_input.get("start_date"):
                    start_date = datetime.strptime(
                        str(med_input.get("start_date")), "%Y-%m-%d"
                    ).date()
                else:
                    start_date = datetime.now(timezone_obj.utc).date()

                # End date
                if med_input.get("end_date"):
                    end_date = datetime.strptime(
                        str(med_input.get("end_date")), "%Y-%m-%d"
                    ).date()
                else:
                    end_date = None

                med = Medication(
                    user_id=user.id,
                    name=med_input.get("name"),
                    dosage=med_input.get("dosage"),
                    start_date=start_date,
                    end_date=end_date,
                    purpose=med_input.get("purpose")
                )
                db.add(med)
                await db.flush()

                for slot in med_input.get("medication_slot"):
                    time_obj = parse_time_string(slot.get('time'))
                    days_of_week = slot.get('days', None)
                    days_array = construct_days_array_from_string(days_of_week)
                    
                    med_time = MedicationTime(
                        medication_id=med.id,
                        time_of_day=time_obj,
                        days_of_week=days_array
                    )
                    db.add(med_time)        

        try:
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
        except Exception as e:
            logger.error(f"Error adding onboarding details to mem0: {e}")
        
        await db.commit()
        address_str = f"{address}, {city}, {postal_code}"
        set_location_coordinates.delay(user_id=user.id, location=address_str)
        send_onboarding_sms(user=user, send_to_caregiver=True)
            
        return {
            "status": "success",
            "message": "Payload processed",
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error processing payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    

@router.post(
    "/red-cross/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new onboarding user",
    description="Create a new onboarding user with the provided details"
)
async def onboard_user_red_cross(
    payload: OnboardingRequestBodyRedCross = Body(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        data = payload.model_dump()
        timezone = data["timezone"]
        stmt = select(Organization).where(Organization.name_slug == "red-cross")
        result = await db.execute(stmt)
        organization = result.scalar_one_or_none()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        # if data.get("call_back_date_time"):
        #     callback_date = data["call_back_date_time"].date()
        #     user_today = date_now_in_timezone(timezone)
        #     record.call_back_date_time = data["call_back_date_time"]
        #     if callback_date == user_today:
        #         onboarding_payload = construct_onboarding_user_payload(record, record.organization.onboarding_agent_id)

        #         dt_utc = convert_to_utc_datetime(tz_name=record.timezone, dt=data["call_back_date_time"])
        #         celery_app.send_task(
        #             "initiate_onboarding_call",
        #             args=[onboarding_payload,],
        #             eta=dt_utc
        #         )

        #         record.onboarding_call_scheduled = True #if the user is calling, no need for call back
            
            # db.add(record)
            # await db.commit()
            # return
        
        # --- check consent --- no need for this if the user is calling
        if not payload.consent_given:
            raise HTTPException(status_code=400, detail="Consent not given")
        
        phone_number = data["phone_number"]
        first_name = data["first_name"]
        last_name = data["last_name"]
        caretaker_phone = data.get("caretaker_phone", None)
        caretaker_name = data.get("caretaker_name", None)
        street_address = data.get("street_address", None)
        city = data.get("city", None)
        post_code = data.get("post_code", None)
        house_number = data.get("house_number", None)
        medication_details = data.get("medication_details", [])
        check_in_details = data.get("check_in_details", {})
        brain_coach = data.get("brain_coach", {})
        caretaker_consent = data.get("caretaker_consent", False)
        health_conditions = data.get("health_conditions", [])
        preferences = data.get("preferences", [])
        mobility = data.get("mobility", [])
        

        caregiver_phone = caretaker_phone
        

        if caregiver_phone:
            caregiver, created = await get_or_create_caregiver(db, caregiver_phone, caretaker_name)
        else:
            caregiver = None

        language = "german" #defaulting to german for red cross for now. 

        user = User(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            street=street_address,
            city=city,
            postal_code=post_code,
            house_number=house_number,
            preferred_communication_channel='phone', #defaulting to phone for red cross for now
            preferred_consultation_language=language,
            health_conditions=", ".join(health_conditions) if health_conditions else None,
            mobility=", ".join(mobility) if mobility else None,
            caretaker_id=caregiver.id if caregiver_phone else None,
            caretaker_consent=caretaker_consent,
            caretaker=caregiver if caregiver_phone else None,
            preferred_reminder_channel="phone",
            preferred_reports_channel=payload.preferred_reports_channel if payload.preferred_reports_channel else "whatsapp",
            timezone=timezone,
            country="Germany",
            organization_id=organization.id,
        )

        db.add(user)
        await db.flush()
        await db.refresh(user)

        wants_brain_coach = brain_coach.get("wants_brain_coach_sessions", False)
        frequency_in_days = brain_coach.get("frequency_in_days", None)
        time_of_day = brain_coach.get("time_of_day", None)
        if wants_brain_coach:
            if not time_of_day:
                time_of_day = "12:00" #defaulting to 12 PM if no time provided

            time_obj = parse_time_string(time_of_day)
            # utc_time = convert_local_time_to_utc_time(time_obj, user.timezone)
            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.brain_coach.value,
                check_in_frequency_days=frequency_in_days if frequency_in_days else 7,
                check_in_time=time_obj
            )
            db.add(check_in)

        wants_daily_check_ins = check_in_details.get("wants_check_ins", False)
        check_in_frequency = check_in_details.get("frequency_in_days", None)
        time_of_day = check_in_details.get("time_of_day", None)
        if wants_daily_check_ins:
            if not time_of_day:
                time_of_day = "09:00" #defaulting to 9 AM if no time provided

            time_obj = parse_time_string(time_of_day)
            # utc_time = convert_local_time_to_utc_time(time_obj, user.timezone)
            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.check_up_call.value,
                check_in_frequency_days=check_in_frequency if check_in_frequency else 7,
                check_in_time=time_obj
            )
            db.add(check_in)

        if medication_details:
            for med_input in medication_details:
                # Start date
                if med_input.get("start_date"):
                    start_date = datetime.strptime(
                        str(med_input.get("start_date")), "%Y-%m-%d"
                    ).date()
                else:
                    start_date = datetime.now(timezone_obj.utc).date()

                # End date
                if med_input.get("end_date"):
                    end_date = datetime.strptime(
                        str(med_input.get("end_date")), "%Y-%m-%d"
                    ).date()
                else:
                    end_date = None

                med = Medication(
                    user_id=user.id,
                    name=med_input.get("name"),
                    dosage=med_input.get("dosage"),
                    start_date=start_date,
                    end_date=end_date,
                    purpose=med_input.get("purpose")
                )
                db.add(med)
                await db.flush()

                for time_str in med_input.get("times", []):
                    time_obj = parse_time_string(time_str)
                    # utc_time = convert_local_time_to_utc_time(time_obj, user.timezone)

                    med_time = MedicationTime(
                        medication_id=med.id,
                        time_of_day=time_obj
                    )
                    db.add(med_time)


        try:
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
        except Exception as e:
            logger.error(f"Error adding onboarding details to mem0: {e}")

        await db.commit()
        address_str = f"{street_address}, {house_number}, {city}, {post_code}, Germany"
        set_location_coordinates.delay(user_id=user.id, location=address_str)
        # send_onboarding_sms(user=user, send_to_caregiver=True) 
            
        return {
            "status": "success",
            "message": "Payload processed",
        }
    except Exception as e:
        await db.rollback()
        logger.error(f"Error processing payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")

@router.post(
    "/zamora/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new onboarding user",
    description="Create a new onboarding user with the provided details"
)
async def onboard_user_zamora(
    payload: OnboardingRequestBodyZamora = Body(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        data = payload.model_dump()
        timezone = data["timezone"]
        stmt = select(Organization).where(Organization.name == "Zamora")
        result = await db.execute(stmt)
        organization = result.scalar_one_or_none()
        if not organization:
            raise HTTPException(status_code=404, detail="Organization not found")
        # if data.get("call_back_date_time"):
        #     callback_date = data["call_back_date_time"].date()
        #     user_today = date_now_in_timezone(timezone)
        #     record.call_back_date_time = data["call_back_date_time"]
        #     if callback_date == user_today:
        #         onboarding_payload = construct_onboarding_user_payload(record, record.organization.onboarding_agent_id)

        #         dt_utc = convert_to_utc_datetime(tz_name=record.timezone, dt=data["call_back_date_time"])
        #         celery_app.send_task(
        #             "initiate_onboarding_call",
        #             args=[onboarding_payload,],
        #             eta=dt_utc
        #         )

        #         record.onboarding_call_scheduled = True #if the user is calling, no need for call back
            
            # db.add(record)
            # await db.commit()
            # return
        
        # --- check consent --- no need for this if the user is calling
        if not payload.consent_given:
            raise HTTPException(status_code=400, detail="Consent not given")
        
        phone_number = data["phone_number"]
        first_name = data["first_name"]
        last_name = data["last_name"]
        caretaker_phone = data.get("caretaker_phone", None)
        caretaker_name = data.get("caretaker_name", None)
        street_address = data.get("street_address", None)
        city = data.get("city", None)
        country = data.get("country", None)
        post_code = data.get("post_code", None)
        house_number = data.get("house_number", None)
        medication_details = data.get("medication_details", [])
        check_in_details = data.get("check_in_details", {})
        brain_coach = data.get("brain_coach", {})
        caretaker_consent = data.get("caretaker_consent", False)
        health_conditions = data.get("health_conditions", [])
        preferences = data.get("preferences", [])
        mobility = data.get("mobility", [])
        

        caregiver_phone = caretaker_phone
        

        if caregiver_phone:
            caregiver, created = await get_or_create_caregiver(db, caregiver_phone, caretaker_name)
        else:
            caregiver = None

        language = "english" 

        user = User(
            first_name=first_name,
            last_name=last_name,
            phone_number=phone_number,
            street=street_address,
            city=city,
            postal_code=post_code,
            house_number=house_number,
            preferred_communication_channel='phone', 
            preferred_consultation_language=language,
            health_conditions=", ".join(health_conditions) if health_conditions else None,
            mobility=", ".join(mobility) if mobility else None,
            caretaker_id=caregiver.id if caregiver_phone else None,
            caretaker_consent=caretaker_consent,
            caretaker=caregiver if caregiver_phone else None,
            preferred_reminder_channel="phone",
            preferred_reports_channel=payload.preferred_reports_channel if payload.preferred_reports_channel else "whatsapp",
            timezone=timezone,
            country=country,
            organization_id=organization.id,
        )

        db.add(user)
        await db.flush()
        await db.refresh(user)

        wants_brain_coach = brain_coach.get("wants_brain_coach_sessions", False)
        frequency_in_days = brain_coach.get("frequency_in_days", None)
        time_of_day = brain_coach.get("time_of_day", None)
        if wants_brain_coach:
            if not time_of_day:
                time_of_day = "12:00" 

            time_obj = parse_time_string(time_of_day)

            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.brain_coach.value,
                check_in_frequency_days=frequency_in_days if frequency_in_days else 7,
                check_in_time=time_obj
            )
            db.add(check_in)

        wants_daily_check_ins = check_in_details.get("wants_check_ins", False)
        check_in_frequency = check_in_details.get("frequency_in_days", None)
        time_of_day = check_in_details.get("time_of_day", None)
        if wants_daily_check_ins:
            if not time_of_day:
                time_of_day = "09:00" 

            time_obj = parse_time_string(time_of_day)

            check_in = UserCheckin(
                user_id=user.id,
                check_in_type=CheckInType.check_up_call.value,
                check_in_frequency_days=check_in_frequency if check_in_frequency else 7,
                check_in_time=time_obj
            )
            db.add(check_in)

        if medication_details:
            for med_input in medication_details:
                # Start date
                if med_input.get("start_date"):
                    start_date = datetime.strptime(
                        str(med_input.get("start_date")), "%Y-%m-%d"
                    ).date()
                else:
                    start_date = datetime.now(timezone_obj.utc).date()

                # End date
                if med_input.get("end_date"):
                    end_date = datetime.strptime(
                        str(med_input.get("end_date")), "%Y-%m-%d"
                    ).date()
                else:
                    end_date = None

                med = Medication(
                    user_id=user.id,
                    name=med_input.get("name"),
                    dosage=med_input.get("dosage"),
                    start_date=start_date,
                    end_date=end_date,
                    purpose=med_input.get("purpose")
                )
                db.add(med)
                await db.flush()

                for time_str in med_input.get("times", []):
                    time_obj = parse_time_string(time_str)

                    med_time = MedicationTime(
                        medication_id=med.id,
                        time_of_day=time_obj
                    )
                    db.add(med_time)


        try:
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
        except Exception as e:
            logger.error(f"Error adding onboarding details to mem0: {e}")

        await db.commit()
        address_str = f"{street_address}, {house_number}, {city}, {post_code}, {country}"
        set_location_coordinates.delay(user_id=user.id, location=address_str)
        # send_onboarding_sms(user=user, send_to_caregiver=True) 
            
        return {
            "status": "success",
            "message": "Payload processed",
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
       

@router.get(
    "/onboarding-users/trend",
    status_code=status.HTTP_200_OK,
    summary="Get onboarding users trend",
    description=(
        "Returns daily onboarding metrics for a UTC calendar window ending today. "
        "Definitions: users = count of onboarding user rows created on that UTC day "
        "(from created_at). completed = count of rows that were completed on that UTC day "
        "(onboarding_status = true and onboarded_at falls on that day). failed = count of rows "
        "that reached failed state on that UTC day (onboarding_status = false, call_attempts >= 3, "
        "and called_at falls on that day)."
    ),
)
async def get_onboarding_users_trend(
    db: AsyncSession = Depends(get_db),
    organization_id: Optional[str] = Query(default=None),
    days: Optional[str] = Query(default="30"),
):
    organization_id_int = _parse_positive_int(organization_id, "organization_id")
    days_int = _parse_positive_int(days, "days", default=30)

    now_utc = datetime.now(timezone_obj.utc)
    end_day = now_utc.date()
    start_day = end_day - timedelta(days=days_int - 1)

    start_dt = datetime.combine(start_day, time.min, tzinfo=timezone_obj.utc)
    end_dt = datetime.combine(end_day + timedelta(days=1), time.min, tzinfo=timezone_obj.utc)

    try:
        created_events = (
            select(
                func.date(OnboardingUser.created_at).label("day"),
                func.count().label("users"),
                literal(0).label("completed"),
                literal(0).label("failed"),
            )
            .where(
                OnboardingUser.organization_id == organization_id_int,
                OnboardingUser.created_at.isnot(None),
                OnboardingUser.created_at >= start_dt,
                OnboardingUser.created_at < end_dt,
            )
            .group_by(func.date(OnboardingUser.created_at))
        )

        completed_events = (
            select(
                func.date(OnboardingUser.onboarded_at).label("day"),
                literal(0).label("users"),
                func.count().label("completed"),
                literal(0).label("failed"),
            )
            .where(
                OnboardingUser.organization_id == organization_id_int,
                OnboardingUser.onboarding_status.is_(True),
                OnboardingUser.onboarded_at.isnot(None),
                OnboardingUser.onboarded_at >= start_dt,
                OnboardingUser.onboarded_at < end_dt,
            )
            .group_by(func.date(OnboardingUser.onboarded_at))
        )

        failed_events = (
            select(
                func.date(OnboardingUser.called_at).label("day"),
                literal(0).label("users"),
                literal(0).label("completed"),
                func.count().label("failed"),
            )
            .where(
                OnboardingUser.organization_id == organization_id_int,
                OnboardingUser.onboarding_status.is_(False),
                OnboardingUser.call_attempts >= 3,
                OnboardingUser.called_at.isnot(None),
                OnboardingUser.called_at >= start_dt,
                OnboardingUser.called_at < end_dt,
            )
            .group_by(func.date(OnboardingUser.called_at))
        )

        union_subquery = union_all(
            created_events, completed_events, failed_events
        ).subquery()

        query = (
            select(
                union_subquery.c.day,
                func.sum(union_subquery.c.users).label("users"),
                func.sum(union_subquery.c.completed).label("completed"),
                func.sum(union_subquery.c.failed).label("failed"),
            )
            .group_by(union_subquery.c.day)
            .order_by(union_subquery.c.day.asc())
        )

        result = await db.execute(query)
        rows = result.mappings().all()
        rows_by_day = {row["day"].isoformat(): row for row in rows}

        data = []
        for i in range(days_int):
            day = start_day + timedelta(days=i)
            day_key = day.isoformat()
            row = rows_by_day.get(day_key)
            data.append(
                {
                    "day": day_key,
                    "users": int(row["users"]) if row else 0,
                    "completed": int(row["completed"]) if row else 0,
                    "failed": int(row["failed"]) if row else 0,
                }
            )

        return {
            "data": data,
            "timestamp": now_utc.isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving onboarding trend: {e}")
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