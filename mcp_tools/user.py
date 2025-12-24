from main import mcp
from sqlalchemy import select
from typing import Optional
from core.database import get_async_session
from pydantic import BaseModel
from models.user import User

class RetrieveUserIdInput(BaseModel):
    phone_number: str

@mcp.tool(
    name="retrieve_user_id",
    description=(
        "Use this tool at the beginning of the call to retrieve the user ID "
        "associated with a phone number."
    )
)
async def retrieve_user_id(input: RetrieveUserIdInput) -> Optional[int]:
    async with get_async_session() as db:
        stmt = select(User).where(User.phone_number == input.phone_number)
        result = await db.execute(stmt)
        user = result.scalars().first()

        return user.id if user else None
