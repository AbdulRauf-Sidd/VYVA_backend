"""
Emergency Contacts API endpoints.

Handles emergency contact management.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_active_user
from models.user import User

router = APIRouter()


@router.get("/contacts")
async def get_emergency_contacts(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get emergency contacts."""
    return {"message": "Emergency contacts endpoint - to be implemented"}


@router.post("/contacts")
async def create_emergency_contact(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create emergency contact."""
    return {"message": "Emergency contact creation - to be implemented"} 