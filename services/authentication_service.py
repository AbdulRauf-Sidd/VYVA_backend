from http.client import HTTPException
from urllib.request import Request
from pytz import utc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from models.user import User
from scripts.authentication_helpers import generate_otp, hash_otp, is_expired, get_current_user_from_session
from models.authentication import OtpSession, UserSession
from datetime import datetime, timedelta
from core.config import settings


async def create_otp_session(db: AsyncSession, contact: str, user_id: int, user_type: str):
    otp = generate_otp()
    otp_hash = hash_otp(otp)
    expires_at = datetime.now(tz=utc) + timedelta(minutes=settings.OTP_TTL_MINUTES)

    if user_type == "user":
        otp_session = OtpSession(contact=contact, otp_hash=otp_hash, expires_at=expires_at, user_id=user_id)
    else:
        otp_session = OtpSession(contact=contact, otp_hash=otp_hash, expires_at=expires_at, caretaker_id=user_id)

    db.add(otp_session)
    await db.commit()
    await db.refresh(otp_session)

    return otp, otp_session.session_id

async def verify_otp_helper(db: AsyncSession, session_id: str, otp: str):
    result = await db.execute(select(OtpSession).where(OtpSession.session_id == session_id))
    otp_session = result.scalar_one_or_none()

    if not otp_session or otp_session.verified:
        return None, None, "Invalid session ID."
    
    if is_expired(otp_session.expires_at):
        return None, None, "OTP has expired."

    if otp_session.attempts >= settings.MAX_ATTEMPTS:
        return None, None, "Maximum attempts exceeded."

    if otp_session.otp_hash == hash_otp(otp):
        otp_session.verified = True
        await db.commit()
        user_id = otp_session.user_id
        caretaker_id = otp_session.caretaker_id
        if user_id:
            return user_id, "user", "OTP verified successfully."
        elif caretaker_id:
            return caretaker_id, "caretaker", "OTP verified successfully."
        return None, None, "User or Caretaker not found."
    else:
        otp_session.attempts += 1
        await db.commit()
        return None, None, "Invalid OTP."
async def delete_otp_session(db: AsyncSession, session_id: str):
    await db.execute(delete(OtpSession).where(OtpSession.session_id == session_id))
    await db.commit()


async def create_user_session(db: AsyncSession, user_id: int, user_type: str, user_agent: str = "", ip_address: str = ""):
    expires_at = datetime.now() + timedelta(minutes=settings.SESSION_DURATION)
    if user_type == "user":
        session = UserSession(user_id=user_id, expires_at=expires_at, user_agent=user_agent, ip_address=ip_address)
    else:
        session = UserSession(caretaker_id=user_id, expires_at=expires_at, user_agent=user_agent, ip_address=ip_address)

    db.add(session)
    await db.commit()
    await db.refresh(session)
    
    return session.session_id

async def get_user_from_session(db: AsyncSession, session_id: str):
    result = await db.execute(select(UserSession).where(
        UserSession.session_id == session_id,
        UserSession.is_active == True,
        UserSession.expires_at > datetime.utcnow()
    ))
    session = result.scalar_one_or_none()
    return session.user_id if session else None

async def invalidate_session(db: AsyncSession, session_id: str):
    await db.execute(
        update(UserSession)
        .where(UserSession.session_id == session_id)
        .values(is_active=False)
    )
    await db.commit()
