from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.authentication_service import create_otp_session, create_user_session, verify_otp_helper
from scripts.authentication_helpers import get_current_caretaker_from_session, is_valid_phone_number, is_expired, get_current_user_from_session, set_cookie
from schemas.responses import StandardSuccessResponse, SessionSuccessResponse, SessionCheckResponse
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload
from models.user import Caretaker, User
from core.config import settings
from models.authentication import CaretakerTempToken, UserTempToken, UserSession, CaretakerSession
from datetime import datetime, timedelta, timezone
from schemas.authentication import PhoneRequest, VerifyOtpRequest
from services.whatsapp_service import whatsapp_service
from scripts.utils import LANGUAGE_MAP

router = APIRouter()

@router.post("/request-otp/", response_model=SessionSuccessResponse)
async def request_otp(request: PhoneRequest, db: AsyncSession = Depends(get_db)):
    phone = request.phone

    if not is_valid_phone_number(phone):
        raise HTTPException(status_code=400, detail="Invalid phone number")

    user_result = await db.execute(select(User).where(User.phone_number == phone))
    user_id = user_result.scalar_one_or_none()
    if not user_id:
        raise HTTPException(status_code=400, detail="No user found with this phone number")
    
    user_id = user_id.id
    otp, session_id = await create_otp_session(db, phone, user_id, user_type="user")
    
    await whatsapp_service.send_otp(phone, otp)
    
    return {
        'success': True,
        "message": "OTP has been sent to your phone",
        "session_id": session_id
    }

@router.post("/caretaker-request-otp/", response_model=SessionSuccessResponse)
async def caretaker_request_otp(request: PhoneRequest, db: AsyncSession = Depends(get_db)):
    phone = request.phone
    if not is_valid_phone_number(phone):
        raise HTTPException(status_code=400, detail="Invalid phone number")
    
    caretaker_result = await db.execute(select(Caretaker).where(Caretaker.phone_number == phone))
    caretaker_id = caretaker_result.scalar_one_or_none()
    if not caretaker_id:
        raise HTTPException(status_code=400, detail="No Caretaker found with this phone number")
    otp, session_id = await create_otp_session(db, phone, caretaker_id.id, user_type="caretaker")
    
    await whatsapp_service.send_otp(phone, otp)
    
    return {
        'success': True,
        "message": "OTP has been sent to your phone",
        "session_id": session_id
    }
        

@router.post("/verify-otp/", response_model=StandardSuccessResponse)
async def verify_otp(request: Request, response: Response, body: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    id, msg = await verify_otp_helper(db, body.session_id, body.otp, 'user')
    if not id:
        raise HTTPException(status_code=400, detail=msg)
    
    session_id = await create_user_session(
        db, 
        id,
        user_type='user',
        user_agent=request.headers.get("User-Agent"), 
        ip_address=request.client.host
    )

    set_cookie(response, session_id)

    return {
        "success": True,
        "message": msg
    }


@router.post("/caretaker-verify-otp/", response_model=StandardSuccessResponse)
async def caretaker_verify_otp(request: Request, response: Response, body: VerifyOtpRequest, db: AsyncSession = Depends(get_db)):
    id, msg = await verify_otp_helper(db, body.session_id, body.otp, 'caretaker')
    if not id:
        raise HTTPException(status_code=400, detail=msg)
    
    session_id = await create_user_session(
        db, 
        id,
        user_type='caretaker',
        user_agent=request.headers.get("User-Agent"), 
        ip_address=request.client.host
    )

    set_cookie(response, session_id)

    user = None
    result = await db.execute(
        select(User)
        .options(selectinload(User.caretaker))
        .where(User.caretaker_id == id)
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

    user_id= token_row.user_id

    session_id = await create_user_session(
        db, 
        user_id, 
        user_type="user",
        user_agent=request.headers.get("User-Agent"), 
        ip_address=request.client.host
    )

    set_cookie(response, session_id)

    return {"success": True, "message": "Magic login successful"}

@router.post("/magic-login-caretaker/", response_model=StandardSuccessResponse)
async def magic_login_caretaker(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):

    data = await request.json()
    token = data.get("token")
    phone = data.get("phone")

    if not token:
        raise HTTPException(status_code=400, detail="Token missing")
    if not phone:
        raise HTTPException(status_code=400, detail="Phone missing")
    
    result = await db.execute(
        select(CaretakerTempToken).where(CaretakerTempToken.token == token)
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

    user_id= token_row.caretaker_id


    session_id = await create_user_session(
        db, 
        user_id, 
        user_type="caretaker",
        user_agent=request.headers.get("User-Agent"), 
        ip_address=request.client.host
    )

    set_cookie(response, session_id)

    return {"success": True, "message": "Magic login successful"}


@router.post("/session/", response_model=SessionCheckResponse)
async def session_auth(
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
    print('session:sdsdsd', session_id)
    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    result = await db.execute(
        select(CaretakerSession).where(CaretakerSession.session_id == session_id)
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


    if not user:
        raise HTTPException(
            status_code=401, 
            detail="Not authenticated: Invalid or expired session"
        )
    
    first_time_agents = [user.symptom_checker_first_time, user.medication_manager_first_time, user.brain_coach_first_time, user.assisstant_first_time, user.social_companion_first_time]

    return {
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "organization_id": user.organization_id,
        "language": LANGUAGE_MAP.get(user.preferred_consultation_language.lower() if user.preferred_consultation_language else "english"),
        "first_time_agents": first_time_agents
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
        "user_id": first_assigned_user.id if first_assigned_user else None,
        "senior_name": first_assigned_user.full_name if first_assigned_user else "User"
    }

@router.post("/logout", response_model=StandardSuccessResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db)
):
    session_id = request.cookies.get(settings.SESSION_COOKIE_NAME)

    if not session_id:
        return {
            "success": True,
            "message": "Logged out successfully"
        }

    await db.execute(
        delete(UserSession).where(UserSession.session_id == session_id)
    )

    await db.execute(
        delete(CaretakerSession).where(CaretakerSession.session_id == session_id)
    )

    await db.commit()

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=True,
        samesite="lax"
    )

    return {
        "success": True,
        "message": "Logged out successfully"
    }