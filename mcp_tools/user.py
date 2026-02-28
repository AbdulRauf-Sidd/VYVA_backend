from schemas.twilio import MessageTypeEnum, SendWhatsappMessage
from .mcp_instance import mcp
from sqlalchemy import select
from typing import Optional
from core.database import get_async_session
from pydantic import BaseModel, EmailStr
from models.user import User, PreferredReportsChannelEnum
from models.user_check_ins import UserCheckin, CheckInType
import enum
import logging
from datetime import time
from models.organization import TwilioWhatsappTemplates, TemplateTypeEnum
from services.whatsapp_service import whatsapp_service

logger = logging.getLogger(__name__)

class RetrieveUserProfileInput(BaseModel):
    phone_number: str

@mcp.tool(
    name="retrieve_user_profile",
    description=(
        "Use this tool at the beginning of the call to retrieve the user's profile "
        "associated with a phone number." \
        "You will pass the user's phone number as input " \
        "You will get the user's ID, full name, email, phone number, timezone, and address as output. " \
        "Use the information to personalize the conversation."
        'AWLAYS USE AT THE BEGINNING OF THE CALL.'
    )
)
async def retrieve_user_profile(input: RetrieveUserProfileInput) -> Optional[dict]:
    async with get_async_session() as db:
        stmt = select(User).where(User.phone_number == input.phone_number)
        result = await db.execute(stmt)
        user = result.scalars().first()
        print('mcp====>', input.phone_number, user)

        if user:
            return {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "phone_number": user.phone_number,
                "timezone": user.timezone,
                "address": user.full_address,
                "preferred_reports_channel": user.preferred_reports_channel,
            }
        return None
    

class RetrieveUserHealthProfileInput(BaseModel):
    user_id: int

@mcp.tool(
    name="retrieve_user_health_profile",
    description=(
        "You will pass the user's id as input " \
        "You will get the user's health profile. which includes the health conditions, and mobility issues" \
        "Use the information to personalize the conversation."
        'AWLAYS USE AT THE BEGINNING OF THE CALL.'
    )
)
async def retrieve_user_health_profile(input: RetrieveUserHealthProfileInput) -> Optional[dict]:
    async with get_async_session() as db:
        stmt = select(User).where(User.id == input.user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()

        if user:
            return {
                "health_conditions": user.health_conditions,
                "mobility_issues": user.mobility,
            }
        return None
    
    
class UpdateUserProfileInput(BaseModel):
    user_id: int
    email: Optional[EmailStr] = None
    preferred_reports_channel: Optional[PreferredReportsChannelEnum] = None

@mcp.tool(
    name="update_user_profile",
    description=(
        "Update user's profile. "
        "You can update email, preferred_reports_channel, or both. "
        "When the user does not have email in the system, you can ask for it and update it using this tool. along with the preferred_reports_channel. " \
        "Pass user_id and the fields to update."
    )
)
async def update_user_profile(
    input: UpdateUserProfileInput
) -> Optional[dict]:

    if input.email is None and input.preferred_reports_channel is None:
        return {
            "error": "No update fields provided. Supply email and/or preferred_reports_channel."
        }

    async with get_async_session() as db:

        stmt = select(User).where(User.id == input.user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()

        if not user:
            return {"error": "User not found"}

        # --- partial updates ---
        if input.email is not None:
            user.email = input.email

        if input.preferred_reports_channel is not None:
            user.preferred_reports_channel = input.preferred_reports_channel

        await db.commit()
        await db.refresh(user)

        return {
            "user_id": user.id,
            "email": user.email,
            "preferred_reports_channel": user.preferred_reports_channel,
            "status": "updated"
        }


class CheckInOperation(str, enum.Enum):
    add = "add"
    delete = "delete"


class ManageUserCheckinInput(BaseModel):
    user_id: int
    check_in_type: CheckInType
    operation: CheckInOperation
    
    # Only required for add/update
    check_in_frequency_days: Optional[int] = None
    check_in_time: Optional[time] = None
    is_active: Optional[bool] = True


@mcp.tool(
    name="manage_user_checkin",
    description=(
        "Use this tool to create, update, or delete a user's check-in configuration "
        "for a specific check-in type (brain_coach or check_up_call). "
        "If operation is 'add', the tool will create the configuration if it does not exist, "
        "or update the existing one if it already exists. "
        "If operation is 'delete', the tool will permanently remove the configuration "
        "for that check-in type. "
        "For 'add' operations, you must provide check_in_frequency_days, and optionally "
        "check_in_time and is_active."
    )
)
async def manage_user_checkin(input: ManageUserCheckinInput) -> dict:

    async with get_async_session() as db:
        try:
            result = await db.execute(
                select(UserCheckin).where(
                    UserCheckin.user_id == input.user_id,
                    UserCheckin.check_in_type == input.check_in_type.value
                )
            )

            existing = result.scalar_one_or_none()

            # -------------------------
            # DELETE
            # -------------------------
            if input.operation == CheckInOperation.delete.value:

                if not existing:
                    return {
                        "success": False,
                        "message": "Check-in configuration does not exist."
                    }

                await db.delete(existing)
                await db.commit()

                return {
                    "success": True,
                    "message": "Check-in configuration deleted."
                }

            # -------------------------
            # ADD / UPDATE
            # -------------------------
            if input.operation == CheckInOperation.add.value:

                if input.check_in_frequency_days is None:
                    return {
                        "success": False,
                        "message": "check_in_frequency_days is required for add operation."
                    }

                if existing:
                    # UPDATE
                    existing.check_in_frequency_days = input.check_in_frequency_days
                    existing.check_in_time = input.check_in_time
                    existing.is_active = input.is_active

                    await db.commit()

                    return {
                        "success": True,
                        "message": "Check-in configuration updated."
                    }

                else:
                    # CREATE
                    new_checkin = UserCheckin(
                        user_id=input.user_id,
                        check_in_type=input.check_in_type.value,
                        check_in_frequency_days=input.check_in_frequency_days,
                        check_in_time=input.check_in_time,
                        is_active=input.is_active
                    )

                    db.add(new_checkin)
                    await db.commit()

                    return {
                        "success": True,
                        "message": "Check-in configuration created."
                    }

        except Exception as e:
            await db.rollback()
            logger.error(f"Error managing check-in: {e}")
            return {
                "success": False,
                "message": "Internal error occurred."
            }



@mcp.tool(
    name="send_whatsapp",
    description=(
        "Use this tool to send a WhatsApp message to a user. "
        "You need to provide the user_id, the message content (optional), and the message type. "
        "The tool will send the formatted WhatsApp message "
        "using the appropriate message template based on the message type."
    )
)
async def send_whatsapp(input: SendWhatsappMessage):
    async with get_async_session() as db:
        stmt = select(User.first_name, User.preferred_consultation_language).where(User.id == input.user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"User not found for WhatsApp message: {input.user_id}")
            return {
                "success": False,
                "message": "User not found."
            }


        if input.message_type == MessageTypeEnum.emergency_contact_alert.value:
            content_variables = {
                "1": user.first_name,
                "2": (input.message or ""),
            }
        else:
            logger.error(f"Unsupported message type: {input.message_type}")
            return {
                "success": False,
                "message": "Unsupported message type."
            }

        template_result = await db.execute(
            select(TwilioWhatsappTemplates.template_id).where(TwilioWhatsappTemplates.language == user.preferred_consultation_language, TwilioWhatsappTemplates.template_type == input.message_type.value)
        )
        template_id = template_result.scalar_one_or_none()

        success = await whatsapp_service.send_message(
            content_sid=template_id,
            content_variables=content_variables,
        )

        if not success:
            logger.error(f"Failed to send WhatsApp message for user {input.user_id}")
            raise {
                "success": False,
                "detail": "Failed to send WhatsApp.",
            }
        return {
            "success": True,
            "message": "WhatsApp sent successfully",
        }