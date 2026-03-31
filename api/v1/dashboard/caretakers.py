from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from models.user import User, Caretaker
from models.organization import Organization

router = APIRouter()

@router.get("/caretakers")
async def get_red_cross_caretakers(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Organization).where(Organization.name.ilike("Red Cross"))
    )
    org = result.scalars().first()

    if not org:
        raise HTTPException(status_code=404, detail="Organization 'Red Cross' not found")

    stmt = (
        select(User, Caretaker)
        .join(Caretaker, User.caretaker_id == Caretaker.id)
        .where(User.organization_id == org.id)
    )

    result = await db.execute(stmt)
    rows = result.all()

    caretakers_list = [
        {
            "user_id": user.id, 
            "user_name": f"{user.first_name} {user.last_name}" if user.first_name else None,
            "user_phone": user.phone_number,
            "caregiver_id": caretaker.id,  
            "caregiver_name": caretaker.name,
            "caregiver_phone": caretaker.phone_number,
            "city": user.city,
        }
        for user, caretaker in rows
    ]

    return {"caretakers": caretakers_list}