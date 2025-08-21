"""
Brain Coach API endpoints.

Handles brain training and cognitive exercises.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_active_user
from models.user import User

router = APIRouter()


@router.get("/sessions")
async def get_brain_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get brain training sessions."""
    return {"message": "Brain coach sessions endpoint - to be implemented"}


@router.post("/sessions")
async def create_brain_session(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Create brain training session."""
    return {"message": "Brain session creation - to be implemented"} 