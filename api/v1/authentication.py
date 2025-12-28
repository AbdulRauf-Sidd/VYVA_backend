from fastapi import APIRouter, Depends, HTTPException, Request, Response, Cookie
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.authentication_service import create_otp_session, create_user_session, verify_otp_helper
from scripts.authentication_helpers import send_otp_via_sms, is_valid_phone_number, is_expired, get_current_user_from_session
from schemas.responses import StandardSuccessResponse, SessionSuccessResponse, SessionCheckResponse
from sqlalchemy import select
from models.user import User
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

    result = await db.execute(select(User).where(User.phone_number == phone))
    if not result.scalar():
        raise HTTPException(status_code=400, detail="No user found with this phone number")
    
    result = (await db.execute(select(User.id).where(User.phone_number == phone)))
    user_id = result.scalar_one()
    otp, session_id = await create_otp_session(db, phone, user_id)
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
    user_id, msg = await verify_otp_helper(db, body.session_id, body.otp)
    if not user_id:
        raise HTTPException(status_code=400, detail=msg)
    
    session_id = await create_user_session(
        db, 
        user_id, 
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
    
    return {
        "success": True,
        "message": msg
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

    session_id = await create_user_session(
        db, 
        token_row.user_id, 
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
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    
    session_id = request.cookies.get("session_id")
    
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

    # Optional: update last activity timestamp
    # session.last_seen_at = datetime.utcnow()
    # await db.commit()

    result = await db.execute(
        select(User).where(User.id == session.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return {
        "success": True,
        "user_id": user.id,
        "first_name": user.first_name
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

    return {
        "user_id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
    }

