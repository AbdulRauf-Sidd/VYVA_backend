import logging
from sqlalchemy import select
from fastapi import APIRouter, Cookie, Cookie, Depends, HTTPException, status
from core.config import settings
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from datetime import time
from pydantic import BaseModel

from core.database import get_db
from models.authentication import UserSession
from schemas.user import UserCreate, UserRead, UserUpdate, UpdateFirstTimeAgentsRequest, UpdateSafetySettingsRequest, SafetySettingsResponse
from models.user import User, Caretaker
from models.user_check_ins import UserCheckin
from scripts.authentication_helpers import get_current_user_from_session


class CaretakerRequest(BaseModel):
    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    language: Optional[str] = None
    wants_medication_alerts: Optional[bool] = None
    wants_fall_alerts: Optional[bool] = None
    preferred_notification_channel: Optional[str] = None

class CaretakerResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone_number: Optional[str] = None
    language: Optional[str] = None
    wants_medication_alerts: Optional[bool] = None
    wants_fall_alerts: Optional[bool] = None
    preferred_notification_channel: Optional[str] = None


class CheckInRequest(BaseModel):
    check_in_type: str        # brain_coach | check_up_call | general_reminders
    check_in_frequency_days: int
    check_in_time: Optional[str] = None  # "HH:MM"

class CheckInResponse(BaseModel):
    id: int
    check_in_type: str
    check_in_frequency_days: int
    check_in_time: Optional[str] = None
    is_active: bool

logger = logging.getLogger(__name__)

router = APIRouter()
    
@router.get("/me", response_model=UserRead, summary="Get current user info")
async def get_current_user_info(
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_from_session(session_id, db)
    return user


@router.put("/me", response_model=UserRead, summary="Update current user info")
async def update_current_user_info(
    payload: UserUpdate,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_from_session(session_id, db)

    update_data = payload.model_dump(exclude_unset=True)
    update_data.pop("password", None)

    for field, value in update_data.items():
        setattr(user, field, value)

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/checkins", response_model=List[CheckInResponse], summary="Get all check-ins for current user")
async def get_checkins(
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_from_session(session_id, db)
    result = await db.execute(select(UserCheckin).where(UserCheckin.user_id == user.id))
    checkins = result.scalars().all()
    return [
        CheckInResponse(
            id=c.id,
            check_in_type=c.check_in_type,
            check_in_frequency_days=c.check_in_frequency_days,
            check_in_time=c.check_in_time.strftime("%H:%M") if c.check_in_time else None,
            is_active=c.is_active,
        )
        for c in checkins
    ]


@router.post("/checkins", response_model=CheckInResponse, summary="Create a check-in for current user")
async def create_checkin(
    payload: CheckInRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_from_session(session_id, db)

    existing = await db.execute(
        select(UserCheckin).where(UserCheckin.user_id == user.id, UserCheckin.check_in_type == payload.check_in_type)
    )
    if existing.scalars().first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Check-in of type '{payload.check_in_type}' already exists")

    check_in_time = None
    if payload.check_in_time:
        h, m = map(int, payload.check_in_time.split(":"))
        check_in_time = time(h, m)

    checkin = UserCheckin(
        user_id=user.id,
        check_in_type=payload.check_in_type,
        check_in_frequency_days=payload.check_in_frequency_days,
        check_in_time=check_in_time,
    )
    db.add(checkin)
    await db.commit()
    await db.refresh(checkin)

    return CheckInResponse(
        id=checkin.id,
        check_in_type=checkin.check_in_type,
        check_in_frequency_days=checkin.check_in_frequency_days,
        check_in_time=checkin.check_in_time.strftime("%H:%M") if checkin.check_in_time else None,
        is_active=checkin.is_active,
    )


@router.put("/checkins/{checkin_id}", response_model=CheckInResponse, summary="Update a check-in")
async def update_checkin(
    checkin_id: int,
    payload: CheckInRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_from_session(session_id, db)

    result = await db.execute(
        select(UserCheckin).where(UserCheckin.id == checkin_id, UserCheckin.user_id == user.id)
    )
    checkin = result.scalars().first()
    if not checkin:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in not found")

    checkin.check_in_type = payload.check_in_type
    checkin.check_in_frequency_days = payload.check_in_frequency_days
    if payload.check_in_time:
        h, m = map(int, payload.check_in_time.split(":"))
        checkin.check_in_time = time(h, m)
    else:
        checkin.check_in_time = None

    await db.commit()
    await db.refresh(checkin)

    return CheckInResponse(
        id=checkin.id,
        check_in_type=checkin.check_in_type,
        check_in_frequency_days=checkin.check_in_frequency_days,
        check_in_time=checkin.check_in_time.strftime("%H:%M") if checkin.check_in_time else None,
        is_active=checkin.is_active,
    )


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


def _build_caretaker_response(c: Caretaker) -> CaretakerResponse:
    return CaretakerResponse(
        id=c.id,
        name=c.name,
        email=c.email,
        phone_number=c.phone_number,
        language=c.language,
        wants_medication_alerts=c.wants_medication_alerts,
        wants_fall_alerts=c.wants_fall_alerts,
        preferred_notification_channel=c.preferred_notification_channel,
    )


@router.get("/caretaker", response_model=CaretakerResponse, summary="Get current user's caretaker")
async def get_caretaker(
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_from_session(session_id, db)
    if not user.caretaker_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No caretaker assigned")
    result = await db.execute(select(Caretaker).where(Caretaker.id == user.caretaker_id))
    caretaker = result.scalars().first()
    if not caretaker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caretaker not found")
    return _build_caretaker_response(caretaker)


@router.post("/caretaker", response_model=CaretakerResponse, summary="Create and assign a caretaker to current user")
async def create_caretaker(
    payload: CaretakerRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_from_session(session_id, db)
    if user.caretaker_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has a caretaker")

    caretaker = Caretaker(
        name=payload.name,
        email=payload.email,
        phone_number=payload.phone_number,
        language=payload.language or "english",
        wants_medication_alerts=payload.wants_medication_alerts if payload.wants_medication_alerts is not None else True,
        wants_fall_alerts=payload.wants_fall_alerts if payload.wants_fall_alerts is not None else False,
        preferred_notification_channel=payload.preferred_notification_channel or "whatsapp",
    )
    db.add(caretaker)
    await db.flush()

    user.caretaker_id = caretaker.id
    await db.commit()
    await db.refresh(caretaker)
    return _build_caretaker_response(caretaker)


@router.put("/caretaker", response_model=CaretakerResponse, summary="Update current user's caretaker")
async def update_caretaker(
    payload: CaretakerRequest,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME),
    db: AsyncSession = Depends(get_db),
):
    user = await get_current_user_from_session(session_id, db)
    if not user.caretaker_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No caretaker assigned")

    result = await db.execute(select(Caretaker).where(Caretaker.id == user.caretaker_id))
    caretaker = result.scalars().first()
    if not caretaker:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Caretaker not found")

    caretaker.name = payload.name
    if payload.email is not None:
        caretaker.email = payload.email
    if payload.phone_number is not None:
        caretaker.phone_number = payload.phone_number
    if payload.language is not None:
        caretaker.language = payload.language
    if payload.wants_medication_alerts is not None:
        caretaker.wants_medication_alerts = payload.wants_medication_alerts
    if payload.wants_fall_alerts is not None:
        caretaker.wants_fall_alerts = payload.wants_fall_alerts
    if payload.preferred_notification_channel is not None:
        caretaker.preferred_notification_channel = payload.preferred_notification_channel

    await db.commit()
    await db.refresh(caretaker)
    return _build_caretaker_response(caretaker)
