from datetime import datetime
from unittest import result
from sqlalchemy import select, func
from fastapi import APIRouter, Depends, HTTPException
from models.onboarding import OnboardingUser, OnboardingLogs
from models.organization import Organization
from core.database import get_db
from schemas.responses import StandardSuccessResponse

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
            "preferred_time": user.preferred_time,
            "onboarding_status": user.onboarding_status,
            "organization_name": org.name,
            "agent_id": org.onboarding_agent_id,
            "onboarding_logs_count": logs_count,
        }
        for user, logs_count in rows
    ]
    
    now_time = datetime.now().time()

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
