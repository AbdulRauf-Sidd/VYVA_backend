# backend/app/api/checkins.py
from fastapi import APIRouter, Query
from typing import List, Optional
from sqlalchemy.future import select
from sqlalchemy import and_
from pydantic import BaseModel
from datetime import time

from core.database import get_async_session
from models.user import User
from models.user_check_ins import UserCheckin
from models.organization import Organization

router = APIRouter()

# Response schema
class CheckInOut(BaseModel):
    id: int
    user_id: int
    userName: str
    userPhone: Optional[str]
    city: Optional[str]
    is_active: bool
    frequency_days: int
    preferred_time: Optional[time]

    class Config:
        orm_mode = True

@router.get("/checkins", response_model=List[CheckInOut])
async def get_checkins(
    search: Optional[str] = Query(None, description="Search by name, phone, or city"),
    filter_status: Optional[str] = Query("all", description="Filter by status: all, active, inactive")
):
    async with get_async_session() as session: 
        stmt = (
            select(UserCheckin, User)
            .join(User, UserCheckin.user_id == User.id)
            .join(Organization, User.organization_id == Organization.id)
            .where(Organization.name.ilike("Red Cross")) 
        )

        if filter_status == "active":
            stmt = stmt.where(UserCheckin.is_active == True)
        elif filter_status == "inactive":
            stmt = stmt.where(UserCheckin.is_active == False)

        result = await session.execute(stmt)
        rows = result.all()

        checkins = []
        for checkin, user in rows:
            full_name = f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email or "Unknown"

            if search:
                s = search.lower()
                if s not in full_name.lower() and \
                   (user.city or "").lower().find(s) == -1 and \
                   (user.phone_number or "").find(s) == -1:
                    continue

            checkins.append(CheckInOut(
                id=checkin.id,
                user_id=user.id,
                userName=full_name,
                userPhone=user.phone_number,
                city=user.city,
                is_active=checkin.is_active,
                frequency_days=checkin.check_in_frequency_days,
                preferred_time=checkin.check_in_time
            ))

        return checkins