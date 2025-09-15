"""
Fall Detection API endpoints.

Handles fall detection and safety monitoring.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import logging
from core.database import get_db
from services.elevenlabs_service import make_fall_detection_batch

logger = logging.getLogger(__name__)

router = APIRouter()



@router.post("")
async def report_fall_event(
    db: AsyncSession = Depends(get_db)
):
    try:
        logger.info(f"======== Fall Dectected =========")
        user = {
            'phone_number': "+923152526525"
        }

        await make_fall_detection_batch(user)
        return {"message": "Fall event reporting - to be implemented"} 
    except Exception as e:
        logger.info(f'Fall detection endpoint failed')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating question"
        )