"""
Profiles API endpoints.

Handles user profile management.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_active_user
# from models.user import User

router = APIRouter()


# @router.get("/me")
# async def get_profile(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get current user profile."""
#     # TODO: Implement profile retrieval
#     return {"message": "Profile endpoint - to be implemented"}


# @router.put("/me")
# async def update_profile(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Update current user profile."""
#     # TODO: Implement profile update
#     return {"message": "Profile update endpoint - to be implemented"} 