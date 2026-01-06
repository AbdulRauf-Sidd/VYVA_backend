from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.authentication_service import create_otp_session, create_user_session, verify_otp_helper
from scripts.authentication_helpers import get_current_caretaker_from_session, send_otp_via_sms, is_valid_phone_number, is_expired, get_current_user_from_session
from schemas.responses import StandardSuccessResponse, SessionSuccessResponse, SessionCheckResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models.user import Caretaker, User
from core.config import settings
from fastapi import Body
from models.authentication import UserTempToken, UserSession
from datetime import datetime, timedelta, timezone
from schemas.authentication import PhoneRequest, VerifyOtpRequest
from services.whatsapp_service import whatsapp_service

router = APIRouter()

@router.post("/request-otp/", response_model=SessionSuccessResponse)
async def request_otp(request: PhoneRequest, db: AsyncSession = Depends(get_db)):
    phone = request.phone

    if not is_valid_phone_number(phone):
        raise HTTPException(status_code=400, detail="Invalid phone number")

    user_result = await db.execute(select(User).where(User.phone_number == phone))
    caretaker_result = await db.execute(select(Caretaker).where(Caretaker.phone_number == phone))
    user_id = user_result.scalar_one_or_none()
    caretaker_id = caretaker_result.scalar_one_or_none()
    if not user_id and not caretaker_id:
        raise HTTPException(status_code=400, detail="No user found with this phone number")
    
    if user_id:
        user_id = user_id.id
    else:
        caretaker_id = caretaker_id.id

    print("Creating OTP session for user_id:", user_id, "caretaker_id:", caretaker_id)
    if user_id is not None:
        otp, session_id = await create_otp_session(db, phone, user_id, user_type="user")
    else:
        otp, session_id = await create_otp_session(db, phone, caretaker_id, user_type="caretaker")

    message = {
        1: otp
    }
    await whatsapp_service.send_otp(phone, message)
    print(otp)

    # await send_otp_via_sms(phone, otp)
    
    return {
        'success': True,
        "message": "OTP has been sent to your phone",
        "session_id": session_id
    }
        

@router.post("/verify-otp/", response_model=StandardSuccessResponse)
async def verify_otp(request: Request, response: Response, body: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    user_id, user_type, msg = await verify_otp_helper(db, body.session_id, body.otp)
    if not user_id:
        raise HTTPException(status_code=400, detail=msg)
    
    session_id = await create_user_session(
        db, 
        user_id,
        user_type=user_type,
        user_agent=request.headers.get("User-Agent"), 
        ip_address=request.client.host
    )

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        # secure=False,       # ❌ must be False for localhost
        # samesite="lax",
        max_age=settings.SESSION_DURATION,
        samesite=None
    )

    user = None
    if user_type == "caretaker":
        result = await db.execute(
            select(User)
            .options(selectinload(User.caretaker))
            .where(User.caretaker_id == user_id)
            .order_by(User.id)
            .limit(1)
        )
        
        user = result.scalar_one_or_none()

    return {
        "success": True,
        "message": msg,
        "data": {
            "user_id": user.id,
            "name": user.caretaker.full_name,
        } if user else None
    }


@router.get("/magic-login", response_model=StandardSuccessResponse)
async def magic_login(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):

    token = request.query_params.get("token")
    if not token:
        raise HTTPException(status_code=400, detail="Token missing")

    result = await db.execute(
        select(UserTempToken).where(UserTempToken.token == token)
    )
    token_row = result.scalar_one_or_none()

    if not token_row:
        raise HTTPException(status_code=400, detail="Invalid token")

    if token_row.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Token expired")

    if token_row.used:
        raise HTTPException(status_code=401, detail="Token already used")

    token_row.used = True
    await db.commit()

    # Create user session
    # expires_at = datetime.utcnow() + timedelta(days=30)
    # db.add(session)
    # await db.commit()
    if token_row.user_id:
        user_id= token_row.user_id
    else:
        user_id= token_row.caretaker_id

    session_id = await create_user_session(
        db, 
        user_id, 
        user_type="user" if token_row.user_id else "caretaker",
        user_agent=request.headers.get("User-Agent"), 
        ip_address=request.client.host
    )

    # Set auth cookie
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        # secure=False,       # ❌ must be False for localhost
        # samesite="lax",
        max_age=settings.SESSION_DURATION,
        samesite=None
    )

    return {"success": True, "message": "Magic login successful"}


@router.post("/session/", response_model=SessionCheckResponse)
async def session_auth(
    # request: Request,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME), 
    db: AsyncSession = Depends(get_db)
):
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(
        select(UserSession).where(UserSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    print(session.user_id, session.caretaker_id)

    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    if is_expired(session.expires_at):
        raise HTTPException(status_code=401, detail="Session expired")
    
    if session.is_active is False:
        raise HTTPException(status_code=401, detail="Session is inactive")

    result = await db.execute(
        select(User).where(User.id == session.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "success": True,
        "user_id": user.id
    }


@router.post("/caretaker-session/", response_model=SessionCheckResponse)
async def caretaker_session_auth(
    # request: Request,
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME), 
    db: AsyncSession = Depends(get_db)
):
    
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(
        select(UserSession).where(UserSession.session_id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")

    if is_expired(session.expires_at):
        raise HTTPException(status_code=401, detail="Session expired")
    
    if session.is_active is False:
        raise HTTPException(status_code=401, detail="Session is inactive")

    result = await db.execute(
        select(Caretaker).where(Caretaker.id == session.caretaker_id)
    )
    caretaker = result.scalar_one_or_none()

    if not caretaker:
        raise HTTPException(status_code=401, detail="Caretaker not found")

    return {
        "success": True,
        "user_id": caretaker.id
    }


@router.get("/profile")
async def read_user_profile(
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME), 
    db: AsyncSession = Depends(get_db) 
):
    if not session_id:
        raise HTTPException(
            status_code=401, 
            detail="Not authenticated: Missing session cookie"
        )

    user = await get_current_user_from_session(session_id, db)
    agent_mappings = {}
    organization_agents = user.organization.agents if user.organization else []
    for agent in organization_agents:
        agent_mappings[agent.name_slug] = agent.agent_id

    if not user:
        raise HTTPException(
            status_code=401, 
            detail="Not authenticated: Invalid or expired session"
        )

    return {
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "organization_id": user.organization_id,
        "agent_mappings": agent_mappings
    }

@router.get("/caretaker-profile")
async def read_caretaker_profile(
    session_id: str = Cookie(None, alias=settings.SESSION_COOKIE_NAME), 
    db: AsyncSession = Depends(get_db) 
):
    if not session_id:
        raise HTTPException(
            status_code=401, 
            detail="Not authenticated: Missing session cookie"
        )

    caretaker = await get_current_caretaker_from_session(session_id, db)
    first_assigned_user = caretaker.assigned_users[0] if caretaker.assigned_users else None
    return {
        "caretaker_id": caretaker.id,
        "name": caretaker.full_name,
        "email": caretaker.email,
        "phone_number": caretaker.phone_number,
        "user_id": first_assigned_user.id if first_assigned_user else None
    }
