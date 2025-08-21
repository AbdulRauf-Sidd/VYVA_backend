"""
Social API endpoints.

Handles social features and connections.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
# from core.security import get_current_active_user
# from models.user import User

router = APIRouter()


# @router.get("/connections")
# async def get_social_connections(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get social connections."""
#     return {"message": "Social connections endpoint - to be implemented"}


# @router.post("/connections")
# async def create_social_connection(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create social connection."""
#     return {"message": "Social connection creation - to be implemented"} 