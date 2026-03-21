from datetime import datetime, timezone
from sqlalchemy import select, func
from fastapi import APIRouter, Depends, HTTPException, status
from models.onboarding import OnboardingUser, OnboardingLogs
from models.organization import Organization
from core.database import get_db
from schemas.responses import StandardSuccessResponse
from scripts.utils import date_time_to_utc, convert_utc_time_to_local_time
from scripts.onboarding_utils import construct_onboarding_user_payload
from celery.result import AsyncResult
from celery_app import celery_app
from schemas.admin import ScheduleCallbackRequest
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/call-queues/list", response_model=StandardSuccessResponse)
async def get_call_queues_status(
    organization_id: int,
    db=Depends(get_db),
):
    org = await db.get(Organization, organization_id)
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")

    stmt = (
        select(
            OnboardingUser,
            func.count(OnboardingLogs.id).label("logs_count")
        )
        .outerjoin(OnboardingLogs)
        .where(OnboardingUser.organization_id == organization_id)
        .group_by(OnboardingUser.id)
    )

    result = await db.execute(stmt)
    rows = result.all()

    table_data = [
        {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone_number": user.phone_number,
            "preferred_time": convert_utc_time_to_local_time(user.preferred_time, user.timezone),
            "onboarding_status": user.onboarding_status,
            "organization_name": org.name,
            "agent_id": org.onboarding_agent_id,
            "onboarding_logs_count": logs_count,
        }
        for user, logs_count in rows
    ]
    
    now_time = datetime.now(timezone.utc).time()

    next_today_stmt = (
        select(OnboardingUser)
        .where(
            OnboardingUser.organization_id == organization_id,
            OnboardingUser.preferred_time.isnot(None),
            OnboardingUser.preferred_time >= now_time,
            OnboardingUser.onboarding_status.is_(False),
        )
        .order_by(OnboardingUser.preferred_time.asc())
        .limit(1)
    )

    result = await db.execute(next_today_stmt)
    next_call = result.scalar_one_or_none()

    if not next_call:
        tomorrow_stmt = (
            select(OnboardingUser)
            .where(
                OnboardingUser.organization_id == organization_id,
                OnboardingUser.preferred_time.isnot(None),
                OnboardingUser.onboarding_status.is_(False),
            )
            .order_by(OnboardingUser.preferred_time.asc())
            .limit(1)
        )

        result = await db.execute(tomorrow_stmt)
        next_call = result.scalar_one_or_none()

    next_call_data = None
    
    today_calls_stmt = (
        select(func.count())
        .select_from(OnboardingUser)
        .where(
            OnboardingUser.organization_id == organization_id,
            OnboardingUser.preferred_time.isnot(None),
            OnboardingUser.preferred_time >= now_time,
            OnboardingUser.onboarding_status.is_(False),
        )
    )

    result = await db.execute(today_calls_stmt)
    calls_scheduled_today = result.scalar() or 0
    
    if next_call:
        next_call_data = {
            "name": next_call.first_name + " " + next_call.last_name,
            "preferred_time": next_call.preferred_time,
        }


    return StandardSuccessResponse(
        message="Call queue fetched successfully",
        data={
            "rows": table_data,
            "infographics": {
                "next_upcoming_call": next_call_data,
                "calls_scheduled_today": calls_scheduled_today,
            },
        },
    )


@router.post("/reschedule-call", status_code=status.HTTP_200_OK)
async def schedule_onboarding_callback(
    payload: ScheduleCallbackRequest,
    db=Depends(get_db),
):
    try:
        user_id = payload.onboarding_user_id
        call_back_date_time = payload.call_back_date_time
        
        # Get user record
        record = await db.get(OnboardingUser, user_id)
        if not record:
            raise HTTPException(status_code=404, detail="Onboarding user not found")
        
        # Check if user is already onboarded
        if record.onboarding_status:
            raise HTTPException(
                status_code=400,
                detail="User is already onboarded. Cannot schedule callback for completed onboarding."
            )
        
        # Revoke existing celery task if one is already scheduled
        if record.onboarding_call_scheduled and record.onboarding_call_task_id:
            try:
                task = AsyncResult(record.onboarding_call_task_id)
                task.revoke(terminate=True)
                logger.info(f"Revoked existing Celery task {record.onboarding_call_task_id} for user {user_id}")
            except Exception as task_e:
                logger.warning(f"Failed to revoke Celery task {record.onboarding_call_task_id}: {task_e}")
                raise HTTPException(
                    status_code=400,
                    detail="Error Revoking celery task."
                )
        
        # Convert incoming datetime to UTC
        dt_utc = date_time_to_utc(call_back_date_time, record.timezone)
        
        # Update record with new callback datetime
        record.preferred_time = dt_utc.time()
        
        # Construct payload and schedule celery task
        try:
            onboarding_payload = construct_onboarding_user_payload(
                record,
                record.organization.onboarding_agent_id
            )
            
            task_result = celery_app.send_task(
                "initiate_onboarding_call",
                args=[onboarding_payload],
                eta=dt_utc
            )
            
            # Store task ID and mark as scheduled
            record.onboarding_call_task_id = task_result.id
            record.onboarding_call_scheduled = True
            
            logger.info(f"Scheduled onboarding call for user {user_id} with task ID {task_result.id} at {dt_utc}")
            
        except Exception as celery_e:
            logger.error(f"Failed to schedule celery task for user {user_id}: {celery_e}")
            raise HTTPException(
                status_code=500,
                detail="Failed to schedule callback task"
            )
        
        # Save to database
        db.add(record)
        await db.commit()
        await db.refresh(record)
        
        return StandardSuccessResponse(
            message="Callback scheduled successfully",
            data={
                "user_id": user_id,
                "task_id": record.onboarding_call_task_id,
                "scheduled_at": dt_utc.isoformat(),
            },
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error scheduling callback for user {payload.onboarding_user_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


