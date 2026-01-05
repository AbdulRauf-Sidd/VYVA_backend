import hashlib
import random
from datetime import datetime, timedelta
from models.organization import Organization
from services.sms_service import sms_service
from pytz import utc
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from models.authentication import UserSession
from models.user import User, Caretaker

def generate_otp(length=4):
    return str(random.randint(10**(length-1), 10**length - 1))

def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()

def is_expired(expires_at) -> bool:
    return datetime.now(tz=utc) > expires_at

async def send_otp_via_sms(phone_number: str, otp: str):
    await sms_service.send_otp(phone_number, otp)
    
def is_valid_phone_number(phone_number: str) -> bool:
    if not phone_number.startswith('+'):
        return False

    digits_only = phone_number[1:]
    if not digits_only.isdigit():
        return False

    return 10 <= len(digits_only) <= 15


async def get_current_user_from_session(
    session_id: str, 
    db: AsyncSession 
) -> User:
    
    if not session_id:
        raise HTTPException(
            status_code=401, 
            detail="Not authenticated: Missing session cookie"
        )

    session_result = await db.execute(
        select(UserSession).where(UserSession.session_id == session_id)
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=401, 
            detail="Invalid session: Session ID not found"
        )

    if is_expired(session.expires_at):
        raise HTTPException(
            status_code=401, 
            detail="Session expired"
        )
    
    if session.is_active is False:
        raise HTTPException(
            status_code=401, 
            detail="Session is inactive"
        )

    result = await db.execute(
    select(User)
        .options(
            selectinload(User.organization)
            .selectinload(Organization.agents)
        )
        .where(User.id == session.user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=401, 
            detail="User not found for session ID"
        )

    return user


async def get_current_caretaker_from_session(
    session_id: str, 
    db: AsyncSession 
) -> User:
    
    if not session_id:
        raise HTTPException(
            status_code=401, 
            detail="Not authenticated: Missing session cookie"
        )

    session_result = await db.execute(
        select(UserSession).where(UserSession.session_id == session_id)
    )
    session = session_result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=401, 
            detail="Invalid session: Session ID not found"
        )

    if is_expired(session.expires_at):
        raise HTTPException(
            status_code=401, 
            detail="Session expired"
        )
    
    if session.is_active is False:
        raise HTTPException(
            status_code=401, 
            detail="Session is inactive"
        )

    result = await db.execute(
    select(Caretaker)
        .where(Caretaker.id == session.caretaker_id)
    )
    caretaker = result.scalar_one_or_none()

    if not caretaker:
        raise HTTPException(
            status_code=401, 
            detail="Caretaker not found for session ID"
        )

    return caretaker