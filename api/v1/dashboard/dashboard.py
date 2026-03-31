from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from models.organization import Organization
from core.database import get_db
from models.user import User, Caretaker
from models.user_check_ins import UserCheckin  # adjust if needed

router = APIRouter()


@router.get("/stats")
async def get_stats(db: AsyncSession = Depends(get_db)):
    total_users_result = await db.execute(
        select(func.count(User.id))
        .join(User.organization)
        .where(Organization.name == "Red Cross")
    )
    total_users = total_users_result.scalar()

    checkins_result = await db.execute(
        select(func.count(UserCheckin.id))
        .join(UserCheckin.user)
        .join(User.organization)
        .where(UserCheckin.is_active == True, Organization.name == "Red Cross")
    )
    checkins_active = checkins_result.scalar()

    caregivers_result = await db.execute(
        select(func.count(Caretaker.id))
        .join(Caretaker.assigned_users)
        .join(User.organization)
        .where(Organization.name == "Red Cross")
    )
    caregivers = caregivers_result.scalar()

    # Hardcoded
    active_alerts = 8
    sensors = 12

    return {
        "total_users": total_users or 0,
        "checkins_active": checkins_active or 0,
        "active_alerts": active_alerts,
        "sensors": sensors,
        "caregivers": caregivers or 0,
    }
    
@router.get("/users-by-city")
async def get_users_by_city(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            User.city,
            func.count(User.id).label("user_count")
        )
        .join(User.organization)
        .where(User.city.isnot(None), Organization.name == "Red Cross")
        .group_by(User.city)
        .order_by(func.count(User.id).desc())
    )

    rows = result.all()

    return [
        {
            "city": row.city,
            "user_count": row.user_count
        }
        for row in rows
    ]