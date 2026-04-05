from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, func
from typing import List, Dict
import logging
import time
from collections import defaultdict
from datetime import date, datetime, timezone, timedelta
import time
from zoneinfo import ZoneInfo
from models.user import User
from models.medication import MedicationStatus, Medication, MedicationLog, MedicationTime
from sqlalchemy.orm import selectinload
from core.database import get_db
from scripts.medication_utils import construct_medication_object_for_reminder, construct_user_payload_for_reminder
from scripts.utils import convert_utc_time_to_local_time, get_zoneinfo_safe, convert_local_time_to_utc_time
from services.medication import MedicationService
from repositories.user import UserRepository
from repositories.medication import MedicationRepository
from schemas.user import UserCreate
from schemas.responses import MedicationOut, MedicationInfoOut, NextDoseOut
from schemas.medication import (
    BulkMedicationRequest,
    MedicationUpdate,
    MedicationInDB,
    BulkMedicationSchema,
    WeeklyScheduleRequest,
    MedicationLogRequest
)
from tasks.utils import schedule_reminder_message


# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/weekly-schedule",
    response_model=dict,
    summary="Get weekly medication schedule for a user"
)
async def get_weekly_medication_schedule(
    payload: WeeklyScheduleRequest,
    db: AsyncSession = Depends(get_db)
):
    weekly_schedule = defaultdict(list)
    taken_medications = 0
    
    try:
        result = await db.execute(
            select(User.timezone).where(User.id == payload.user_id)
        )
        user_timezone = result.scalar_one_or_none()
        now_utc = datetime.now(timezone.utc)
        user_now = now_utc.astimezone(ZoneInfo(user_timezone))
        today = user_now.date()
        result = await db.execute(
            select(Medication)
            .where(
                Medication.user_id == payload.user_id,
                Medication.start_date <= payload.date_end,
                or_(
                    Medication.end_date.is_(None),
                    Medication.end_date >= payload.date_start
                )
            )
            .options(
                selectinload(Medication.times_of_day)
                .selectinload(MedicationTime.logs)
            )
        )
        medications = result.scalars().unique().all()

        now_utc = datetime.now(timezone.utc)
        user_now = now_utc.astimezone(ZoneInfo(user_timezone))
        today = user_now.date()
        current_time = user_now.time()
        current_date = payload.date_start
        end_date = payload.date_end

        while current_date <= end_date:
            day_name = current_date.strftime("%A")
            for med in medications:
                
                if med.end_date and med.end_date < current_date:
                    continue  # Skip medications that have ended before the current date
                if med.start_date and med.start_date > current_date:
                    continue  

                for time_entry in med.times_of_day:
                    medication_time = time_entry.time_of_day
                    if not medication_time:
                        continue
                    # Check if log exists for that date
                    log = next(
                        (log for log in time_entry.logs
                         if log.created_at.date() == current_date),
                        None
                    )
                    if payload.is_present:
                        if current_date < today:
                            # Past day → behave like historical
                            status_value = log.status if log else MedicationStatus.unconfirmed.value
                        elif current_date == today:
                            # Today logic
                            if medication_time <= current_time:
                                # Dose time has passed
                                status_value = log.status if log else MedicationStatus.unconfirmed.value
                            else:
                                # Future dose today
                                status_value = MedicationStatus.upcoming.value
                        else:
                            # Future days
                            status_value = MedicationStatus.upcoming.value
                    else:
                        status_value = log.status if log else MedicationStatus.unconfirmed.value
                    
                    if status_value == "taken":
                        taken_medications += 1

                    weekly_schedule[day_name].append({
                        "medication_name": med.name,
                        "dosage": med.dosage,
                        "time": time_entry.time_of_day.strftime("%H:%M"),
                        "notes": time_entry.notes,
                        "status": status_value
                    })

            current_date += timedelta(days=1)

        return {
            "schedule": dict(weekly_schedule)
        }

    except Exception as e:
        logger.error(
            f"Request : Failed to fetch weekly medication schedule for user {payload.user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch weekly medication schedule"
        )

@router.get("/weekly-overview/{user_id}")
async def get_weekly_overview(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User.timezone).where(User.id == user_id)
    )
    user_timezone = result.scalar_one_or_none()

    if not user_timezone:
        raise HTTPException(status_code=404, detail="User not found")

    tz = ZoneInfo(user_timezone)

    now_utc = datetime.now(timezone.utc)
    user_now = now_utc.astimezone(tz)
    today = now_utc.date()
    current_time = now_utc.time()

    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    result = await db.execute(
        select(Medication)
        .where(
            Medication.user_id == user_id,
            Medication.start_date <= sunday,
            or_(
                Medication.end_date.is_(None),
                Medication.end_date >= monday
            )
        )
        .options(
            selectinload(Medication.times_of_day)
            .selectinload(MedicationTime.logs)
        )
    )

    medications = result.scalars().unique().all()

    total = 0
    total_taken = 0

    upcoming_medicine = None
    upcoming_datetime = None

    log_lookup = {}
    for med in medications:
        for time_entry in med.times_of_day:
            for log in time_entry.logs:
                log_date = log.created_at.astimezone(tz).date()
                key = (time_entry.id, log_date)
                log_lookup[key] = log

    current_date = monday

    upcoming_medicines_today = []

    while current_date <= sunday:
        for med in medications:
            for time_entry in med.times_of_day:
                medication_time = time_entry.time_of_day
                if not medication_time:
                    continue

                local_time = convert_utc_time_to_local_time(
                            medication_time,
                            user_timezone
                        )

                log = log_lookup.get((time_entry.id, current_date))
                if log and log.status == MedicationStatus.taken.value:
                    total_taken += 1

                dose_datetime = datetime.combine(
                    current_date,
                    medication_time,
                    tzinfo=tz
                )

                if current_date < today:
                    total += 1 

                if current_date == today:
                    status = log.status if log else MedicationStatus.unconfirmed.value
                    if medication_time >= current_time:
                        status = MedicationStatus.upcoming.value
                    else:
                        total += 1

                    if med.is_active:
                        upcoming_medicines_today.append({
                            "name": med.name,
                            "time": local_time.strftime("%H:%M"),
                            "status": status
                        })

                if dose_datetime > now_utc and med.is_active:
                    if upcoming_datetime is None or dose_datetime < upcoming_datetime:
                        upcoming_datetime = dose_datetime
                        upcoming_medicine = {
                            "name": med.name,
                            "time": local_time.strftime("%H:%M")
                        }

        current_date += timedelta(days=1)
    return {
        "total_scheduled_current_week": total,
        "total_taken_this_week": total_taken,
        "adherence_percentage": round((total_taken / total) * 100, 2) if total else 0.0,
        "upcoming_medicine": upcoming_medicine,
        "todays_medicines": upcoming_medicines_today
    }


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
        if user_id <= 0:
            raise ValueError("Invalid user ID")

        stmt = (
            select(Medication)
            .where(Medication.user_id == user_id, Medication.is_active == True)
            .options(selectinload(Medication.times_of_day), selectinload(Medication.user))
        )
        result = await db.execute(stmt)
        medications = result.scalars().all()

        response: List[MedicationOut] = []

        for med in medications:
            response.append(
                MedicationOut(
                    id=med.id,
                    user_id=med.user_id,
                    name=med.name,
                    dosage=med.dosage,
                    start_date=med.start_date,
                    end_date=med.end_date,
                    purpose=med.purpose,
                    side_effects=med.side_effects,
                    notes=med.notes,
                    times_of_day=[
                        {
                            "id": t.id,
                            "medication_id": t.medication_id,
                            "time_of_day": convert_utc_time_to_local_time(t.time_of_day, med.user.timezone),
                            "notes": t.notes,
                        }
                        for t in med.times_of_day
                    ],
                )
            )

        duration = time.time() - start_time
        logger.info(f"Request {request_id}: Found {len(response)} medications for user {user_id} in {duration:.2f}s")

        if not response:
            logger.info(f"Request {request_id}: No medications found for user {user_id}")

        return response

    except ValueError as e:
        logger.warning(f"Request {request_id}: Invalid user ID {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Request {request_id}: Failed to fetch medications for user {user_id}: {str(e)}", exc_info=True)
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

    try:
        if user_id <= 0:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")

        # Fetch medications with times and logs eagerly loaded
        result = await db.execute(
            select(Medication)
            .options(
                selectinload(Medication.times_of_day),
                selectinload(Medication.logs),
                selectinload()
            )
            .where(Medication.user_id == user_id)
        )
        medications = result.scalars().all()

        now_utc = datetime.now(timezone.utc)
        today = now_utc.date()
        week_start = today - timedelta(days=today.weekday())
        week_end = week_start + timedelta(days=6)

        # Weekly adherence
        weekly_logs = [
            log for med in medications for log in med.logs
            if log.created_at and week_start <= log.created_at.date() <= week_end
        ]
        total_logs = len(weekly_logs)
        taken_logs = sum(1 for log in weekly_logs if log.status == MedicationStatus.taken.value)
        adherence_percentage = round((taken_logs / total_logs) * 100, 2) if total_logs else 0.0

        # Determine user timezone
        user = await db.get(User, user_id)
        user_tz = timezone.utc
        if user and getattr(user, "timezone", None):
            try:
                user_tz = ZoneInfo(user.timezone)
            except Exception:
                user_tz = timezone.utc
        # Upcoming doses
        upcoming_doses = []
        for med in medications:
            for t in med.times_of_day:
                if not t.time_of_day:
                    continue
                candidate_dt = datetime.combine(now_utc.date(), t.time_of_day, timezone.utc)
                if candidate_dt >= now_utc.time():
                    upcoming_doses.append((candidate_dt, med.name))

        next_dose = None
        if upcoming_doses:
            next_time, med_name = min(upcoming_doses, key=lambda x: x[0])
            next_dose = NextDoseOut(medication_name=med_name, time=convert_utc_time_to_local_time(next_time, user_tz))

        return MedicationInfoOut(
            weekly_adherence_percentage=adherence_percentage,
            doses_taken_percentage=adherence_percentage,
            active_medications=medications,
            next_dose=next_dose
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch medication info: {str(e)}"
        )
    
def get_week_start(d: date) -> date:
    return d - timedelta(days=d.weekday())

@router.get("/adherence-history/{user_id}")
async def get_adherence_history(
    user_id: int,
    weeks: int = 8,
    db: AsyncSession = Depends(get_db),
):
    try:
        today = date.today()
        history = []

        for i in range(weeks):
            week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)

            # ---- Scheduled doses ----
            meds_stmt = (
                select(
                    Medication.id,
                    Medication.start_date,
                    Medication.end_date,
                    func.count(MedicationTime.id).label("times_per_day")
                )
                .join(MedicationTime)
                .where(Medication.user_id == user_id)
                .group_by(Medication.id)
            )

            meds_result = await db.execute(meds_stmt)
            total_scheduled = 0

            for med_id, start_date, end_date, times_per_day in meds_result:
                med_start = start_date or week_start
                med_end = end_date or week_end

                active_days = max(
                    0,
                    (min(med_end, week_end) - max(med_start, week_start)).days + 1
                )

                total_scheduled += active_days * times_per_day

            # ---- Taken doses ----
            logs_stmt = (
                select(MedicationLog.medication_id, MedicationLog.taken_at, MedicationLog.created_at)
                .where(
                    MedicationLog.user_id == user_id,
                    func.date(func.coalesce(
                        MedicationLog.taken_at,
                        MedicationLog.created_at
                    )) >= week_start,
                    func.date(func.coalesce(
                        MedicationLog.taken_at,
                        MedicationLog.created_at
                    )) <= week_end,
                )
            )
            
            logs_result = await db.execute(logs_stmt)
            
            taken_map = set()
            
            for med_id, taken_at, created_at in logs_result:
                if not taken_at:
                    continue
                log_date = (taken_at).date()
                taken_map.add((med_id, log_date))
            
            total_taken = len(taken_map)

            adherence = (
                round((total_taken / total_scheduled) * 100, 1)
                if total_scheduled > 0
                else 0
            )

            history.append({
                "week_start": week_start.isoformat(),
                "week_end": week_end.isoformat(),
                "scheduled": total_scheduled,
                "taken": total_taken,
                "adherence": adherence
            })

        return {
            "success": True,
            "data": list(reversed(history))
        }

    except HTTPException:
        raise  # propagate HTTPExceptions as-is

    except Exception as e:
        logger.exception(f"Failed to fetch adherence history for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error while fetching adherence history"
        )


@router.post(
    "/log-medication",
    summary="Update medication logs"
)
async def update_medication_log_api(
    request: MedicationLogRequest,
    db: AsyncSession = Depends(get_db)
):
    try:
        if not request.user_id:
            raise ValueError("User ID is required.")
        
        if not request.medication_logs:
            raise ValueError("Medication logs are required.")
        
        # Fetch user timezone
        stmt = select(User.timezone).where(User.id == request.user_id)
        result = await db.execute(stmt)
        user_timezone = result.scalars().first()
        if not user_timezone:
            raise ValueError(f"User with ID {request.user_id} not found.")
        tz = get_zoneinfo_safe(user_timezone)
        now_utc = datetime.now(timezone.utc)
        user_now = now_utc.astimezone(tz)
        
        missed_meds = []
        for med in request.medication_logs:
            med_taken = med.taken
            if not med_taken:
                missed_meds.append({"medication_id": med.medication_id, "time_id": med.time_id})
            # Find the latest log for this medication and time
            stmt = select(MedicationLog).where(
                MedicationLog.medication_id == med.medication_id,
                MedicationLog.medication_time_id == med.time_id,
                MedicationLog.user_id == request.user_id
            ).order_by(MedicationLog.created_at.desc()).limit(1)
            result = await db.execute(stmt)
            log = result.scalars().first()

            if log:
                log.status = MedicationStatus.taken.value if med_taken else MedicationStatus.missed.value
                log.taken_at = now_utc if med_taken else None
                log.taken_at_local = user_now if med_taken else None
            else:
                # Fallback: create new log if none exists
                log = MedicationLog(
                    medication_id=med.medication_id,
                    medication_time_id=med.time_id,
                    user_id=request.user_id,
                    taken_at=now_utc if med_taken else None,
                    taken_at_local=user_now if med_taken else None,
                    status=MedicationStatus.taken.value if med_taken else MedicationStatus.missed.value
                )
                db.add(log)

        await db.commit()

        if request.reminder:
            reminder_time = request.reminder_time
            if not reminder_time:
                logger.info("No reminder time provided, defaulting to 15 minutes from now")
                reminder_time = user_now + timedelta(minutes=15).time()
            
            utc_time = convert_local_time_to_utc_time(reminder_time, user_timezone)
            dt_utc = datetime.combine(now_utc.date(), utc_time, tzinfo=timezone.utc)
            med_payload = construct_medication_object_for_reminder(missed_meds)
            user_payload = construct_user_payload_for_reminder(request.user_id)
            schedule_reminder_message(
                    payload={
                        **user_payload,
                        "medications": med_payload
                    },
                    dt_utc=dt_utc,
                    preferred_reminder_channel=user_payload.get("preferred_reminder_channel", "phone")
                )
            message = "meds scheduled for reminder. "

            return {
                "success": True,
                "message": message
            }
        else:
            return {
                "success": True,
                "message": "Congratulate User on taking medications."
            }

    except ValueError as e:
        logger.warning(f"Medication Log: Validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Medication Log: Failed to update medication logs for user {request.user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update medication logs"
        )