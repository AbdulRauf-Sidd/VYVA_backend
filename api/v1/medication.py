from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_, select, func
from typing import List, Dict
import logging
import time
from collections import defaultdict
from datetime import date, datetime, time as time_type, timezone, timedelta
import time
from zoneinfo import ZoneInfo
from models.user import User
from models.medication import MedicationStatus, Medication, MedicationLog, MedicationTime, MedicationPause
from models.user_check_ins import UserCheckin, CheckInType, ScheduledSession, CheckinLog, CheckinLogStatusEnum
from sqlalchemy.orm import selectinload
from core.database import get_db
from scripts.medication_utils import construct_medication_object_for_reminder, construct_user_payload_for_reminder, medication_days_mapping_string_to_int, medication_days_mapping_int_to_string, construct_days_array_from_string
from scripts.authentication_helpers import get_current_user_from_session
from core.config import settings
from scripts.utils import convert_utc_time_to_local_time, get_zoneinfo_safe, convert_local_time_to_utc_time
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
    MedicationLogRequest,
    MedicationCreateRequest,
    MedicationUpdateRequest,
    MedicationDetail,
    MedicationTimeDetail,
    ScheduledItem,
    TodayScheduleResponse,
    UpdateCheckinLogRequest,
    CheckinLogResponse,
    MedicationPauseRequest,
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
        if not payload.user_id or not payload.date_start or not payload.date_end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="user_id, date_start, and date_end are required."
            )

        result = await db.execute(
            select(User.timezone).where(User.id == payload.user_id)
        )
        user_timezone = result.scalar_one_or_none()
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

                    if time_entry.days_of_week:
                        day_num = medication_days_mapping_string_to_int.get(day_name.lower())
                        if day_num not in time_entry.days_of_week:
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
        day_name = current_date.strftime("%A")
        for med in medications:
            for time_entry in med.times_of_day:
                medication_time = time_entry.time_of_day
                if not medication_time:
                    continue

                if time_entry.days_of_week:
                    day_num = medication_days_mapping_string_to_int.get(day_name.lower())
                    if day_num not in time_entry.days_of_week:
                        continue


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
                            "time": medication_time.strftime("%H:%M"),
                            "status": status
                        })

                if dose_datetime > now_utc and med.is_active:
                    if upcoming_datetime is None or dose_datetime < upcoming_datetime:
                        upcoming_datetime = dose_datetime
                        upcoming_medicine = {
                            "name": med.name,
                            "time": medication_time.strftime("%H:%M")
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
                            "time_of_day": t.time_of_day.strftime("%H:%M") if t.time_of_day else None,
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
            next_dose = NextDoseOut(medication_name=med_name, time=next_time)

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


def _build_time_detail(med_time: MedicationTime, time_str: str, days_str) -> MedicationTimeDetail:
    return MedicationTimeDetail(
        id=med_time.id,
        medication_id=med_time.medication_id,
        time=time_str,
        days=days_str,
    )


def _build_medication_detail(med: Medication, times: list, is_paused: bool = False) -> MedicationDetail:
    return MedicationDetail(
        id=med.id,
        name=med.name,
        dosage=med.dosage,
        purpose=med.purpose,
        start_date=med.start_date,
        end_date=med.end_date,
        is_paused=is_paused,
        times=times,
    )


@router.get(
    "/medications_details",
    response_model=List[MedicationDetail],
    summary="Get active medications for authenticated user"
)
async def get_my_medications(
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user_from_session(session_id, db)
        today = date.today()

        stmt = (
            select(Medication)
            .where(
                Medication.user_id == user.id,
                Medication.is_active == True,
                or_(
                    Medication.end_date.is_(None),
                    Medication.end_date >= today,
                ),
            )
            .options(selectinload(Medication.times_of_day), selectinload(Medication.pauses))
            .order_by(Medication.id)
        )
        result = await db.execute(stmt)
        medications = result.scalars().all()

        data = []
        for med in medications:
            times = []
            for t in med.times_of_day:
                days_str = (
                    [medication_days_mapping_int_to_string.get(d) for d in t.days_of_week]
                    if t.days_of_week
                    else None
                )
                times.append(
                    MedicationTimeDetail(
                        id=t.id,
                        medication_id=t.medication_id,
                        time=t.time_of_day.strftime("%H:%M") if t.time_of_day else None,
                        days=days_str,
                    )
                )
            is_paused = any(p.pause_end is None for p in med.pauses)
            data.append(_build_medication_detail(med, times, is_paused=is_paused))

        return data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get My Medications: Failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch medications"
        )


@router.post(
    "/medications_details",
    response_model=MedicationDetail,
    summary="Create a new medication for authenticated user"
)
async def create_my_medication(
    payload: MedicationCreateRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user_from_session(session_id, db)

        tz = get_zoneinfo_safe(user.timezone)
        now_utc = datetime.now(timezone.utc)
        start_date = now_utc.astimezone(tz).date()

        new_med = Medication(
            user_id=user.id,
            name=payload.name,
            dosage=payload.dosage,
            purpose=payload.purpose,
            start_date=start_date,
            is_active=True,
        )
        db.add(new_med)
        await db.flush()

        times = []
        for slot in payload.medication_slot:
            hours, minutes = map(int, slot.time.split(":"))
            time_obj = time_type(hour=hours, minute=minutes)
            days_array = construct_days_array_from_string(slot.days)
            med_time = MedicationTime(
                medication=new_med,
                time_of_day=time_obj,
                days_of_week=days_array,
            )
            db.add(med_time)
            await db.flush()
            times.append(
                MedicationTimeDetail(
                    id=med_time.id,
                    medication_id=new_med.id,
                    time=slot.time,
                    days=slot.days,
                )
            )

        await db.commit()
        return _build_medication_detail(new_med, times)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Create Medication: Validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Create Medication: Failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create medication"
        )


@router.put(
    "/medication_details/{medication_id}",
    response_model=MedicationDetail,
    summary="Update a medication for authenticated user (creates new record, preserves history)"
)
async def update_my_medication(
    medication_id: int,
    payload: MedicationUpdateRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user_from_session(session_id, db)

        stmt = (
            select(Medication)
            .where(Medication.id == medication_id, Medication.user_id == user.id)
            .options(selectinload(Medication.times_of_day))
        )
        result = await db.execute(stmt)
        old_med = result.scalars().first()

        if not old_med:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

        tz = get_zoneinfo_safe(user.timezone)
        now_utc = datetime.now(timezone.utc)
        user_today = now_utc.astimezone(tz).date()

        old_med.end_date = user_today
        old_med.is_active = False
        old_med.disabled_at = now_utc
        await db.flush()

        new_med = Medication(
            user_id=user.id,
            name=payload.name if payload.name is not None else old_med.name,
            dosage=payload.dosage if payload.dosage is not None else old_med.dosage,
            purpose=payload.purpose if payload.purpose is not None else old_med.purpose,
            start_date=user_today,
            end_date=None,
            notes=old_med.notes,
            side_effects=old_med.side_effects,
            is_active=True,
        )
        db.add(new_med)
        await db.flush()

        times = []
        if payload.medication_slot is not None:
            for slot in payload.medication_slot:
                hours, minutes = map(int, slot.time.split(":"))
                time_obj = time_type(hour=hours, minute=minutes)
                days_array = construct_days_array_from_string(slot.days)
                med_time = MedicationTime(
                    medication=new_med,
                    time_of_day=time_obj,
                    days_of_week=days_array,
                )
                db.add(med_time)
                await db.flush()
                times.append(
                    MedicationTimeDetail(
                        id=med_time.id,
                        medication_id=new_med.id,
                        time=slot.time,
                        days=slot.days,
                    )
                )
        else:
            for t in old_med.times_of_day:
                med_time = MedicationTime(
                    medication=new_med,
                    time_of_day=t.time_of_day,
                    days_of_week=t.days_of_week,
                )
                db.add(med_time)
                await db.flush()
                days_str = (
                    [medication_days_mapping_int_to_string.get(d) for d in t.days_of_week]
                    if t.days_of_week
                    else None
                )
                times.append(
                    MedicationTimeDetail(
                        id=med_time.id,
                        medication_id=new_med.id,
                        time=t.time_of_day.strftime("%H:%M") if t.time_of_day else None,
                        days=days_str,
                    )
                )

        await db.commit()
        return _build_medication_detail(new_med, times)

    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Update Medication: Validation failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Update Medication: Failed for medication {medication_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update medication"
        )


@router.put(
    "/medication_details/{medication_id}/pause",
    summary="Pause or unpause a medication"
)
async def pause_medication(
    medication_id: int,
    payload: MedicationPauseRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user_from_session(session_id, db)

        result = await db.execute(
            select(Medication).where(Medication.id == medication_id, Medication.user_id == user.id)
        )
        medication = result.scalars().first()

        if not medication:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Medication not found")

        tz = get_zoneinfo_safe(user.timezone)
        today = datetime.now(timezone.utc).astimezone(tz).date()

        if payload.paused:
            active_pause = await db.execute(
                select(MedicationPause).where(
                    MedicationPause.schedule_id == medication_id,
                    MedicationPause.pause_end == None,
                )
            )
            if active_pause.scalars().first():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Medication is already paused")

            db.add(MedicationPause(schedule_id=medication_id, pause_start=today))
        else:
            active_pause = await db.execute(
                select(MedicationPause).where(
                    MedicationPause.schedule_id == medication_id,
                    MedicationPause.pause_end == None,
                )
            )
            pause = active_pause.scalars().first()
            if not pause:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Medication is not paused")

            pause.pause_end = today

        await db.commit()
        return {"success": True, "paused": payload.paused}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pause Medication: Failed for medication {medication_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update medication pause status"
        )


@router.get(
    "/today-schedule",
    response_model=TodayScheduleResponse,
    summary="Get all upcoming items for the authenticated user today"
)
async def get_today_schedule(
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user_from_session(session_id, db)

        tz = get_zoneinfo_safe(user.timezone)
        now_utc = datetime.now(timezone.utc)
        user_now = now_utc.astimezone(tz)
        user_today = user_now.date()
        current_local_time = user_now.time().replace(tzinfo=None)
        today_weekday = user_today.weekday()  # Mon=0, Sun=6

        items: list[ScheduledItem] = []

        # ── 1. Upcoming medications ───────────────────────────────────────────
        med_stmt = (
            select(Medication)
            .where(
                Medication.user_id == user.id,
                Medication.is_active == True,
                or_(
                    Medication.end_date.is_(None),
                    Medication.end_date >= user_today,
                ),
            )
            .options(selectinload(Medication.times_of_day))
        )
        med_result = await db.execute(med_stmt)
        for med in med_result.scalars().all():
            for t in med.times_of_day:
                if not t.time_of_day:
                    continue
                if t.days_of_week and today_weekday not in t.days_of_week:
                    continue
                if t.time_of_day > current_local_time:
                    items.append(ScheduledItem(
                        type="medication",
                        time=t.time_of_day.strftime("%H:%M"),
                        details={
                            "medication_id": med.id,
                            "medication_time_id": t.id,
                            "name": med.name,
                            "dosage": med.dosage,
                            "purpose": med.purpose,
                        },
                    ))

        # ── 2. Upcoming check-in / brain coach calls ──────────────────────────
        # Mirrors schedule_check_in_calls_for_hour: only schedule if the last
        # session is old enough (>= check_in_frequency_days) or there is none.
        checkin_stmt = (
            select(UserCheckin)
            .where(
                UserCheckin.user_id == user.id,
                UserCheckin.is_active == True,
            )
            .options(selectinload(UserCheckin.scheduled_sessions))
        )
        checkin_result = await db.execute(checkin_stmt)
        for checkin in checkin_result.scalars().all():
            if not checkin.check_in_time:
                continue

            last_session = max(
                checkin.scheduled_sessions,
                key=lambda s: s.scheduled_at,
                default=None,
            )
            days_since = (user_today - last_session.scheduled_at.date()).days if last_session else None
            should_schedule = last_session is None or days_since >= checkin.check_in_frequency_days

            if not should_schedule:
                continue
            if checkin.check_in_time <= current_local_time:
                continue

            existing_log = await db.execute(
                select(CheckinLog)
                .where(
                    CheckinLog.checkin_id == checkin.id,
                    func.date(CheckinLog.date) == user_today,
                    CheckinLog.status != CheckinLogStatusEnum.unconfirmed.value,
                )
                .limit(1)
            )
            if existing_log.scalars().first():
                continue

            items.append(ScheduledItem(
                type=checkin.check_in_type,
                time=checkin.check_in_time.strftime("%H:%M"),
                details={"check_in_id": checkin.id},
            ))

        # ── 3. Upcoming general reminders today ───────────────────────────────
        tomorrow_start_utc = (
            datetime.combine(user_today + timedelta(days=1), time_type(0, 0), tzinfo=tz)
            .astimezone(timezone.utc)
        )
        reminder_stmt = (
            select(ScheduledSession)
            .where(
                ScheduledSession.user_id == user.id,
                ScheduledSession.session_type == CheckInType.general_reminders.value,
                ScheduledSession.is_cancelled == False,
                ScheduledSession.is_completed == False,
                ScheduledSession.scheduled_at > now_utc,
                ScheduledSession.scheduled_at < tomorrow_start_utc,
            )
            .order_by(ScheduledSession.scheduled_at.asc())
        )
        reminder_result = await db.execute(reminder_stmt)
        for r in reminder_result.scalars().all():
            local_dt = r.scheduled_at.astimezone(tz)
            items.append(ScheduledItem(
                type="general_reminder",
                time=local_dt.strftime("%H:%M"),
                details={
                    "id": r.id,
                    "purpose": (r.metadata_ or {}).get("purpose"),
                    "scheduled_at": r.scheduled_at.isoformat(),
                },
            ))

        items.sort(key=lambda x: x.time)

        return TodayScheduleResponse(items=items)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get Today Schedule: Failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch today's schedule"
        )


@router.put(
    "/checkin-log/{log_id}",
    response_model=CheckinLogResponse,
    summary="Update check-in log status"
)
async def update_checkin_log_status(
    log_id: int,
    payload: UpdateCheckinLogRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user_from_session(session_id, db)


        result = await db.execute(
            select(UserCheckin)
            .where(UserCheckin.id == log_id, CheckinLog.user_id == user.id)
        )
        checkin = result.scalars().first()

        if not checkin:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found")
        
        log = CheckinLog(
            checkin_id=checkin.id,
            user_id=user.id,
            status=payload.status.value,
            date=datetime.now(timezone.utc)
        )
        
        db.add(log)

        await db.commit()
        await db.refresh(log)

        return CheckinLogResponse(
            id=log.id,
            checkin_id=log.checkin_id,
            status=log.status,
            date=log.date,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update Checkin Log: Failed for log {log_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update check-in log"
        )