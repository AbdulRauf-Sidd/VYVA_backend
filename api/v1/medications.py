"""
Medications API endpoints.

Handles medication management.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_active_user
# from models.user import User

router = APIRouter()


# @router.get("/")
# async def get_medications(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get user medications."""
#     return {"message": "Medications endpoint - to be implemented"}


# @router.post("/")
# async def create_medication(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create medication."""
#     return {"message": "Medication creation - to be implemented"} 