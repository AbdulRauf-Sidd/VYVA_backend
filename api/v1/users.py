from sqlalchemy import select
from fastapi import APIRouter, Cookie, Cookie, Depends, HTTPException, status
from core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from core.database import get_db
from models.authentication import UserSession
from schemas.user import UserCreate, UserRead, UserUpdate, UpdateFirstTimeAgentsRequest
from repositories.user import UserRepository
from models.user import User

router = APIRouter()
    
@router.put("/first-time-agents", summary="Update first time agents for user")
async def update_profile_first_time_agents(
    payload: UpdateFirstTimeAgentsRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User)
        .join(UserSession)
        .where(UserSession.session_id == session_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    print("Updating first_time_agents for user:", user.id, payload.first_time_agents)

    (
        user.symptom_checker_first_time,
        user.medication_manager_first_time,
        user.brain_coach_first_time,
        user.assisstant_first_time,
        user.social_companion_first_time,
    ) = payload.first_time_agents

    await db.commit()

    return {
        "success": True,
        "message": "first_time_agents updated successfully",
    }