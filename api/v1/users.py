import logging
from sqlalchemy import select
from fastapi import APIRouter, Cookie, Cookie, Depends, HTTPException, status
from core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from core.database import get_db
from models.authentication import UserSession
from schemas.user import UserCreate, UserRead, UserUpdate, UpdateFirstTimeAgentsRequest, UpdateSafetySettingsRequest, SafetySettingsResponse
from repositories.user import UserRepository
from models.user import User
from scripts.authentication_helpers import get_current_user_from_session

logger = logging.getLogger(__name__)

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


@router.put(
    "/safety-settings",
    response_model=SafetySettingsResponse,
    summary="Update emergency and fall detection settings for authenticated user"
)
async def update_safety_settings(
    payload: UpdateSafetySettingsRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    try:
        user = await get_current_user_from_session(session_id, db)

        if payload.emergency_call_to_caretaker is not None:
            user.emergency_call_to_caretaker = payload.emergency_call_to_caretaker
        if payload.emergency_call_to_government_services is not None:
            user.emergency_call_to_government_services = payload.emergency_call_to_government_services
        if payload.emergency_protocol_status is not None:
            user.emergency_protocol_status = payload.emergency_protocol_status
        if payload.fall_detection_activation is not None:
            user.fall_detection_activation = payload.fall_detection_activation
        if payload.fall_auto_alert_to_caregiver is not None:
            user.fall_auto_alert_to_caregiver = payload.fall_auto_alert_to_caregiver

        await db.commit()
        await db.refresh(user)

        return SafetySettingsResponse(
            emergency_call_to_caretaker=user.emergency_call_to_caretaker,
            emergency_call_to_government_services=user.emergency_call_to_government_services,
            emergency_protocol_status=user.emergency_protocol_status,
            fall_detection_activation=user.fall_detection_activation,
            fall_auto_alert_to_caregiver=user.fall_auto_alert_to_caregiver,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Update Safety Settings: Failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update safety settings"
        )