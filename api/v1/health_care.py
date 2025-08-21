"""
Health & Care API endpoints.

Handles health and care data management.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_active_user
# from models.user import User

router = APIRouter()


# @router.get("/")
# async def get_health_records(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Get health records."""
#     return {"message": "Health care endpoint - to be implemented"}


# @router.post("/")
# async def create_health_record(
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ):
#     """Create health record."""
#     return {"message": "Health record creation - to be implemented"} 