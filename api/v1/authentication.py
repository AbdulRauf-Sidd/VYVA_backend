from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from services.authentication_service import create_otp_session, create_user_session, verify_otp_helper
from scripts.authentication_helpers import send_otp_via_sms, is_valid_phone_number
from schemas.responses import StandardSuccessResponse
from sqlalchemy import select
from models.user import User
from core.config import settings
from fastapi import Body


router = APIRouter()

@router.post("/request-otp/", response_model=StandardSuccessResponse)
async def request_otp(phone: str = Body(...), db: AsyncSession = Depends(get_db)):
    if not is_valid_phone_number(phone):
        raise HTTPException(status_code=400, detail="Invalid phone number")

    if not await db.execute(select(User).where(User.phone_number == phone)).scalar():
        raise HTTPException(status_code=400, detail="No user found with this phone number")
    
    user_id = (await db.execute(select(User.id).where(User.phone_number == phone))).scalar_one()

    otp, session_id = await create_otp_session(db, phone, user_id)
    send_otp_via_sms(phone, otp)
    
    return {
        'success': True,
        "message": "OTP has been sent to your phone",
        "session_id": session_id
    }
        

@router.post("/v1/auth/verify-otp", response_model=StandardSuccessResponse)
async def verify_otp(request: Request, response: Response, session_id: str, otp: str, db: AsyncSession = Depends(get_db)):
    user_id, msg = await verify_otp_helper(db, session_id, otp)
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
        max_age=settings.SESSION_DURATION,
        samesite="lax"
    )
    
    return {
        "success": True,
        "message": msg
    }

# @router.delete("/v1/auth/otp-session/{session_id}", response_model=StandardSuccessResponse)
# async def delete_otp_route(session_id: str, db: AsyncSession = Depends(get_db)):
#     await delete_otp_session(db, session_id)
#     return {
#         "success": True,
#         "message": "Session deleted"
#     }