from fastapi import APIRouter, Depends
import logging
from models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from scripts.utils import get_iso_language, get_user_local_dt, is_doctor_available
from services.helpers import construct_welcome_message_for_main_agent
from schemas.twilio import TwilioPersonalizationRequest


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/personalization")
async def personalize_call(
    payload: TwilioPersonalizationRequest,
    db: AsyncSession = Depends(get_db)
):
    caller_id = payload.caller_id
    if not caller_id.startswith('+'):
        caller_id = '+' + caller_id
    stmt = select(User).where(User.phone_number == caller_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    local_time = get_user_local_dt(user.timezone) if user and user.timezone else ""

    if not user:
        return {
            "dynamic_variables": {
                "user_id": "",
                "address": "",
                "first_name": "",
                "name": "",
                'email': "",
                "phone_number": payload.caller_id,
                "local_time": "",
                "timezone": "",
                'preferred_reports_channel': "",
                'health_conditions': "",
                'mobility_issues': "",
                "conversation_id": payload.conversation_id,
                "is_registered": False,
                "app_user": False,
                "doctor_available": is_doctor_available(None)
            },
        }

    first_time = not bool(user.social_companion_first_time)
    
    iso_language = get_iso_language(user.preferred_consultation_language)
    first_message = construct_welcome_message_for_main_agent(user.first_name, iso_language, first_time)

    address = user.full_address
    email = user.email
    timezone = user.timezone

    logger.info(f"address: {address}, email: {email}, timezone: {timezone}")


    return {
        "conversation_config_override": {
            "agent": {
                "first_message": first_message,
            }
        },
        "dynamic_variables": {
            "user_id": user.id,
            "address": user.full_address,
            "first_name": user.first_name,
            "name": user.full_name,
            "local_time": local_time.time().strftime("%H:%M") if local_time else "",
            'email': user.email,
            "phone_number": user.phone_number,
            'preferred_reports_channel': user.preferred_reports_channel,
            'health_conditions': user.health_conditions,
            'mobility_issues': user.mobility,
            "timezone": timezone,
            "conversation_id": payload.conversation_id,
            "is_registered": True,
            "app_user": False,
            "doctor_available": is_doctor_available(timezone)
        },
    }


@router.post("/rc/personalization")
async def personalize_call(
    payload: TwilioPersonalizationRequest,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.phone_number == payload.caller_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    local_time = get_user_local_dt(user.timezone) if user and user.timezone else ""

    if not user:
        return {
        "dynamic_variables": {
            "user_id": "",
            "first_name": "",
            "name": "",
            "phone_number": payload.caller_id,
            'email': "",
            "local_time": "",
            "timezone": "",
            'preferred_reports_channel': "",
            'health_conditions': "",
            'mobility_issues': "",
            "conversation_id": payload.conversation_id,
            "is_registered": False,
            "app_user": False
        },
    }

    first_time = not bool(user.social_companion_first_time)
    
    iso_language = get_iso_language(user.preferred_consultation_language)
    first_message = construct_welcome_message_for_main_agent(user.first_name, iso_language, first_time)


    return {
        "conversation_config_override": {
            "agent": {
                "first_message": first_message,
            }
        },
        "dynamic_variables": {
            "user_id": user.id,
            "address": user.full_address,
            "first_name": user.first_name,
            "name": user.full_name,
            "local_time": local_time.time().strftime("%H:%M") if local_time else "",
            'email': user.email,
            "phone_number": user.phone_number,
            'preferred_reports_channel': user.preferred_reports_channel,
            'health_conditions': user.health_conditions,
            'mobility_issues': user.mobility,
            "timezone": user.timezone,
            "conversation_id": payload.conversation_id,
            "is_registered": True,
            "app_user": False
        },
    }