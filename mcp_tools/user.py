from .mcp_instance import mcp
from sqlalchemy import select
from typing import Optional
from core.database import get_async_session
from pydantic import BaseModel, EmailStr
from models.user import User, PreferredReportsChannelEnum

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
