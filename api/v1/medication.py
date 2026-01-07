from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from models.user import User
from models.medication import MedicationStatus, Medication
from sqlalchemy.orm import selectinload
from core.database import get_db
from services.medication import MedicationService
from repositories.user import UserRepository
from repositories.medication import MedicationRepository
from schemas.user import UserCreate
from schemas.responses import MedicationEntry, WeeklyScheduleResponse, MedicationOut, MedicationInfoOut, NextDoseOut
from schemas.medication import (
    BulkMedicationRequest,
    MedicationCreate,
    MedicationUpdate,
    MedicationInDB,
    BulkMedicationSchema
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "",
    response_model=List[MedicationInDB],
    status_code=status.HTTP_201_CREATED,
    summary="Create multiple medications"
)
async def bulk_create_medications(
    request: BulkMedicationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create multiple medications with their times in a single request.
    """
    start_time = time.time()
    request_id = f"bulk_create_{int(start_time * 1000)}"
    
    logger.info(
        f"Request {request_id}: Starting bulk medication creation for user {request.user_id} "
        f"with {len(request.medication_details)} medications"
    )
    
    try:
        full_name = request.name
        if full_name:
            name_parts = full_name.strip().split()
            first_name = name_parts[0]
            last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else None
        else:
            first_name = None
            last_name = None

        # last_name = request.last_name or ""
        user_repo = UserRepository(db)
        user_data = UserCreate(
                first_name=first_name,
                last_name=last_name,
                email=request.email,
                phone_number=request.phone,
                wants_reminders=True,
                missed_dose_alerts=True,
                takes_medication=True,
                preferred_channel=request.channel,
                wants_caretaker_alerts=request.caretaker_alerts,
                caretaker_preferred_channel=request.caretaker_channel,
                caretaker_name=request.caretaker_name,
                caretaker_email=request.caretaker_email,
                caretaker_phone_number=request.caretaker_phone
            )
        user = await user_repo.create_user(user_data)
        logger.info(f"Request {request_id}: Created user {user.id} for medication assignment")
        medication_request = BulkMedicationSchema(
            medication_details=request.medication_details,
            user_id=user.id,
        )
        logger.info(f"Request {request_id}: request body {request}")
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        logger.info(
            f"Request {request_id}: Processing medications: {[med.name for med in request.medication_details]}"
        )
        
        result = await medication_service.process_bulk_medication_request(medication_request)
        
        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Successfully created {len(result)} medications "
            f"for user {medication_request.user_id} in {duration:.2f}s"
        )
        
        return result
        
    except ValueError as e:
        logger.warning(
            f"Request {request_id}: Validation failed for user {request.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Request {request_id}: Unexpected error creating medications for user {request.user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create medications"
        )

@router.get(
    "/user/{user_id}",
    response_model=List[MedicationInDB],
    summary="Get all medications for a user"
)
async def get_user_medications(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve all medications for a specific user, including medication times.
    """
    start_time = time.time()
    request_id = f"get_user_{user_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Fetching medications for user {user_id}")
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        result = await medication_service.get_user_medications(user_id)
        
        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Found {len(result)} medications for user {user_id} "
            f"in {duration:.2f}s"
        )
        
        if not result:
            logger.info(f"Request {request_id}: No medications found for user {user_id}")
        
        return result
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Invalid user ID {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to fetch medications for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch medications"
        )

@router.get(
    "/{medication_id}",
    response_model=MedicationInDB,
    summary="Get a specific medication"
)
async def get_medication(
    medication_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific medication by ID, including its times.
    """
    start_time = time.time()
    request_id = f"get_med_{medication_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Fetching medication {medication_id}")
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        result = await medication_service.get_medication(medication_id)
        
        duration = time.time() - start_time
        if result:
            logger.info(
                f"Request {request_id}: Found medication '{result.name}' (ID: {medication_id}) "
                f"in {duration:.2f}s"
            )
        else:
            logger.warning(f"Request {request_id}: Medication {medication_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medication not found"
            )
            
        return result
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Invalid medication ID {medication_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to fetch medication {medication_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch medication"
        )

@router.put(
    "/{medication_id}",
    response_model=MedicationInDB,
    summary="Update a medication"
)
async def update_medication(
    medication_id: int,
    update_data: MedicationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a medication and its times.
    """
    start_time = time.time()
    request_id = f"update_med_{medication_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Updating medication {medication_id}")
    logger.info(f"Request {request_id}: Update data: {update_data.dict(exclude_unset=True)}")
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        result = await medication_service.update_medication(medication_id, update_data)
        
        duration = time.time() - start_time
        if result:
            logger.info(
                f"Request {request_id}: Successfully updated medication '{result.name}' "
                f"(ID: {medication_id}) in {duration:.2f}s"
            )
        else:
            logger.warning(f"Request {request_id}: Medication {medication_id} not found for update")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medication not found"
            )
            
        return result
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Validation failed for medication {medication_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to update medication {medication_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update medication"
        )

@router.put(
    "/bulk/{user_id}",
    response_model=List[MedicationInDB],
    summary="Bulk update user medications"
)
async def bulk_update_medications(
    user_id: int,
    medications_data: List[MedicationUpdate],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk update multiple medications for a user.
    """
    start_time = time.time()
    request_id = f"bulk_update_{user_id}_{int(start_time * 1000)}"
    
    logger.info(
        f"Request {request_id}: Starting bulk update for user {user_id} "
        f"with {len(medications_data)} medication updates"
    )
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        # Get user's current medications
        current_medications = await medication_service.get_user_medications(user_id)
        logger.info(f"Request {request_id}: Found {len(current_medications)} current medications")
        
        updated_medications = []
        for medication in current_medications:
            # Find corresponding update data
            update_data = next((med for med in medications_data if getattr(med, 'id', None) == medication.id), None)
            if update_data:
                logger.info(f"Request {request_id}: Updating medication {medication.id}")
                result = await medication_service.update_medication(medication.id, update_data)
                if result:
                    updated_medications.append(result)
        
        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Successfully updated {len(updated_medications)} medications "
            f"for user {user_id} in {duration:.2f}s"
        )
        
        return updated_medications
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Validation failed for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to bulk update medications for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update medications"
        )

@router.get(
    "/weekly-schedule/{user_id}",
    response_model=WeeklyScheduleResponse,
    summary="Get weekly medication schedule for a user"
)
async def get_weekly_medication_schedule(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    request_id = f"weekly_schedule_{user_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Fetching weekly medication schedule for user {user_id}")
    
    try:
        # Fetch medications with their times
        result = await db.execute(
            select(Medication)
            .where(Medication.user_id == user_id)
            .options(selectinload(Medication.times_of_day))
        )
        medications = result.scalars().all()

        weekly_schedule = defaultdict(list)

        for med in medications:
            for time_entry in med.times_of_day:
                if time_entry.time_of_day:
                    day_name = time_entry.time_of_day.strftime("%A")  # e.g., "Monday"
                    time_str = time_entry.time_of_day.strftime("%H:%M")
                else:
                    day_name = "Unscheduled"
                    time_str = None

                weekly_schedule[day_name].append({
                    "medication_name": med.name,  # <--- must match Pydantic field
                    "dosage": med.dosage,
                    "time": time_str or "",        # optional string
                    "notes": time_entry.notes
                })

        # Ensure all days exist
        for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday", "Unscheduled"]:
            weekly_schedule.setdefault(day, [])

        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Retrieved weekly medication schedule for user {user_id} "
            f"in {duration:.2f}s"
        )

        return dict(weekly_schedule)
        
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to fetch weekly medication schedule for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch weekly medication schedule"
        )
        
@router.get(
    "/medications/{user_id}",
    response_model=List[MedicationOut],
    summary="Get all medications for a user including times"
)
async def get_all_medications_with_times(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    request_id = f"get_all_meds_{user_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Fetching all medications with times for user {user_id}")
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        result = await medication_service.get_user_medications(user_id)
        
        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Found {len(result)} medications with times for user {user_id} "
            f"in {duration:.2f}s"
        )
        
        if not result:
            logger.info(f"Request {request_id}: No medications found for user {user_id}")
        
        return result
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Invalid user ID {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to fetch medications for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch medications"
        )
        
@router.get(
    "/medication-times/{user_id}",
    response_model=List[MedicationOut],
    summary="Get all medications with times for a user"
)
async def get_medications_with_times(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    request_id = f"get_meds_times_{user_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Fetching medications with times for user {user_id}")
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        result = await medication_service.get_user_medications(user_id)
        
        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Found {len(result)} medications with times for user {user_id} "
            f"in {duration:.2f}s"
        )
        
        if not result:
            logger.info(f"Request {request_id}: No medications found for user {user_id}")
        
        return result
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Invalid user ID {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to fetch medications for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch medications"
        )
        
@router.get(
    "/medication-info/{user_id}",
    response_model=MedicationInfoOut,
    summary="Get detailed medication info for a user"
)
async def get_detailed_medication_info(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    start_time = time.time()
    request_id = f"get_med_info_{user_id}_{int(start_time * 1000)}"

    logger.info(f"Request {request_id}: Fetching detailed medication info for user {user_id}")

    try:
        if user_id <= 0:
            raise ValueError("Invalid user ID")

        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)

        medications = await medication_service.get_user_medications(user_id)

        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        weekly_logs = []
        for med in medications:
            for log in med.logs:
                if log.created_at:
                    log_date = log.created_at.date()
                    if week_start <= log_date <= week_end:
                        weekly_logs.append(log)

        total_logs = len(weekly_logs)
        taken_logs = sum(
            1 for log in weekly_logs if log.status == MedicationStatus.TAKEN
        )

        adherence_percentage = (
            round((taken_logs / total_logs) * 100, 2) if total_logs > 0 else 0.0
        )

        user = await db.get(User, user_id)
        user_tz = timezone.utc
        if user and getattr(user, "timezone", None):
            try:
                user_tz = ZoneInfo(user.timezone)
            except Exception:
                logger.warning(
                    f"Request {request_id}: Invalid timezone for user {user_id}, falling back to UTC"
                )

        now_local = now_utc.astimezone(user_tz)

        upcoming_doses = []
        for med in medications:
            for t in med.times_of_day:
                if not t.time_of_day:
                    continue

                candidate_dt = datetime.combine(
                    now_local.date(),
                    t.time_of_day,
                    tzinfo=user_tz
                )

                if candidate_dt >= now_local:
                    upcoming_doses.append((candidate_dt, med.name))

        next_dose = None
        if upcoming_doses:
            next_time, med_name = min(upcoming_doses, key=lambda x: x[0])
            next_dose = NextDoseOut(
                medication_name=med_name,
                time=next_time
            )

        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Medication info computed for user {user_id} "
            f"in {duration:.2f}s"
        )

        return MedicationInfoOut(
            weekly_adherence_percentage=adherence_percentage,
            doses_taken_percentage=adherence_percentage,
            active_medications=medications,
            next_dose=next_dose
        )

    except ValueError as e:
        logger.warning(f"Request {request_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to fetch medication info for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch medication info"
        )