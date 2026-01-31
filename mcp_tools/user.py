from .mcp_instance import mcp
from sqlalchemy import select
from typing import Optional
from core.database import get_async_session
from pydantic import BaseModel
from models.user import User

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
    
    