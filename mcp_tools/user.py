from schemas.twilio import MessageTypeEnum, SendWhatsappMessage
from .mcp_instance import mcp
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import Optional
from core.database import get_async_session
from pydantic import BaseModel, EmailStr
from models.user import User, PreferredReportsChannelEnum
from models.user_check_ins import CheckinLog, UserCheckin, CheckInType
import enum
import logging
from datetime import time
from models.organization import OrganizationAgents, TwilioWhatsappTemplates, TemplateTypeEnum, AgentTypeEnum
from services.whatsapp_service import whatsapp_service
from services.elevenlabs_service import call_agent
from schemas.tools import EmergencyResponderRequest

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
    retrieve = "retrieve"


class ManageUserCheckinInput(BaseModel):
    user_id: int
    check_in_type: CheckInType
    operation: CheckInOperation
    
    # Only required for add/update
    check_in_frequency_days: Optional[int] = None
    check_in_time: Optional[time] = None


@mcp.tool(
    name="manage_user_checkin",
    description=(
        "Use this tool to create, update, delete, or retrieve a user's check-in configuration "
        "for a specific check-in type (brain_coach or check_up_call)."

        "The following user terms should be interpreted as a request for a check_up_call:"
        "wellness_call, control_call, follow-up_call, check-up_call, check-in_call, status_call."

        "If operation is 'add', the tool will create the configuration if it does not exist,"
        "or update the existing one if it already exists."

        "If operation is 'delete', the tool will permanently remove the configuration"
        "for that check-in type."

        "If operation is 'retrieve', the tool will return the current configuration"
        "for that check-in type if it exists."
        
        "For 'add' operations, you must provide check_in_frequency_days, and optionally"
        "check_in_time."
    )
)
async def manage_user_checkin(input: ManageUserCheckinInput) -> dict:

    async with get_async_session() as db:
        try:
            user = await db.get(User, input.user_id)
            if not user:
                return {
                    "success": False,
                    "message": "User not found."
                }

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

                # utc_time = convert_local_time_to_utc_time(input.check_in_time, user.timezone)
                if existing:
                    # UPDATE
                    existing.check_in_frequency_days = input.check_in_frequency_days
                    existing.check_in_time = input.check_in_time

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
                        is_active=True
                    )

                    db.add(new_checkin)
                    await db.commit()

                    return {
                        "success": True,
                        "message": "Check-in configuration created."
                    }
            if input.operation == CheckInOperation.retrieve.value:
                if not existing:
                    return {
                        "success": False,
                        "message": "Check-in configuration does not exist."
                    }
                # check_time_local = convert_utc_time_to_local_time(existing.check_in_time, user.timezone)
                return {
                    "success": True,
                    "check_in_type": existing.check_in_type,
                    "check_in_frequency_days": existing.check_in_frequency_days,
                    "check_in_time": existing.check_in_time,
                }

        except Exception as e:
            await db.rollback()
            logger.error(f"Error managing check-in: {e}")
            return {
                "success": False,
                "message": "Internal error occurred."
            }

class CheckInLogStatusEnum(str, enum.Enum):
    reported_okay = "reported_okay"
    reported_issue = "reported_issue"

class CheckInTypeEnum(str, enum.Enum):
    brain_coach = "brain_coach"
    check_up_call = "check_up_call"
    

class UpdateCallLogStatusInput(BaseModel):
    user_id: int
    status: CheckInLogStatusEnum
    checkin_type: CheckInTypeEnum
    

@mcp.tool(
    name="update_call_log_status",
    description=(
        "Update the latest call log for the given user. "
        "Use this tool whenever the user user says they received a check in call and wanted to update it's status"
        "the options for status are 'reported_okay' and 'reported_issue'"
        "The options for checkin_type are 'brain_coach' and 'check_up_call'"
        "Provide user_id and status, and checkin_type. The tool will find the latest call log for that user "
        "and checkin type, and update its status."
    )
)
async def update_call_log_status(input: UpdateCallLogStatusInput) -> dict:
    async with get_async_session() as db:
        stmt = select(CheckinLog).join(
            UserCheckin, CheckinLog.checkin_id == UserCheckin.id
        ).where(
            UserCheckin.user_id == input.user_id,
            UserCheckin.check_in_type == input.checkin_type.value
        ).order_by(CheckinLog.date.desc()).limit(1)
        result = await db.execute(stmt)
        log = result.scalars().first()

        if not log:
            raise ValueError(f"No call log found for user {input.user_id}.")

        log.status = input.status

        await db.commit()
        await db.refresh(log)

        return {
            "success": True
        }


@mcp.tool(
    name="send_whatsapp",
    description=(
        "Use this tool to send a WhatsApp message to a user. "
        "You need to provide the user_id, the message content (optional), and the message type. "
        "The tool will send the formatted WhatsApp message "
        "using the appropriate message template based on the message type."
        "if it's emergency, use emergency_contact_alert message_type"
    )
)
async def send_whatsapp(input: SendWhatsappMessage):
    async with get_async_session() as db:
        logger.info(f"Processing send_whatsapp for user_id: {input.user_id}, message_type: {input.message_type}")
        stmt = select(User).options(
            selectinload(User.caretaker)
        ).where(User.id == input.user_id)
        result = await db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user:
            logger.warning(f"User not found for WhatsApp message: {input.user_id}")
            return {
                "success": False,
                "message": "User not found."
            }
        
        if not user.caretaker:
            logger.info(f"No caretaker assigned for user {input.user_id}, skipping WhatsApp message.")
            return {
                "success": False,
                "message": "No caretaker assigned to user."
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
            to_phone=user.caretaker.phone_number,
            template_id=template_id,
            template_data=content_variables,
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
    

@mcp.tool(
    name="emergency_responder",
    description=(
        "Send an emergency alert by invoking the org's responder agent. "
        "Provide user_id and emergency_message."
    )
)
async def emergency_responder(req: EmergencyResponderRequest):
    try:
        async with get_async_session() as db:
            logger.info(f"Emergency responder endpoint called for user_id: {req.user_id}, message: {req.emergency_message}")

            # Fetch user with organization relationship
            user_result = await db.execute(
                select(User).options(
                    selectinload(User.organization)
                ).where(User.id == req.user_id)
            )
            user = user_result.scalar_one_or_none()

            if not user:
                logger.warning(f"User not found: {req.user_id}")
                return {
                    "status_code": 404,
                    "detail": f"User not found for user_id: {req.user_id}"
                }

            if not user.organization:
                logger.warning(f"User {req.user_id} has no organization assigned")
                return {
                    "status_code": 400,
                    "detail": "User has no organization assigned"
                }

            # Get organization's emergency responder agent
            agent_result = await db.execute(
                select(OrganizationAgents).where(
                    OrganizationAgents.organization_id == user.organization.id,
                    OrganizationAgents.agent_type == AgentTypeEnum.emergency_responder.value,
                    OrganizationAgents.is_active == True
                )
            )
            agent = agent_result.scalar_one_or_none()

            if not agent:
                logger.warning(f"No active emergency responder agent found for organization {user.organization.id}")
                return {
                    "status_code": 404,
                    "detail": "No emergency responder agent found for this organization"
                }

            # Build payload with user details
            payload = {
                "full_name": user.full_name,
                "address": user.full_address,
                "phone_number": user.phone_number,
                "emergency": req.emergency_message,
                "language": user.preferred_consultation_language or "spanish",
                "phone_number_id": user.organization.phone_number_id
            }

            # Call general agent function
            response = call_agent(agent_id=agent.agent_id, phone_number="+34664338991", payload=payload) #DUMMY

            logger.info(f"Emergency responder agent response: {response}")
            return response
        
    except Exception as e:
        logger.error(f"Error in emergency_responder endpoint: {str(e)}", exc_info=True)
        return {
            "status_code": 500
        }


