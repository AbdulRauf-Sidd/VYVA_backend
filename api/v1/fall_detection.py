"""
Fall Detection API endpoints.

Handles fall detection and safety monitoring.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging
from core.database import get_db
from services.elevenlabs_service import make_fall_detection_call
from models.emergency_numbers import EmergencyNumber, EmergencyNumberTypeEnum

logger = logging.getLogger(__name__)

router = APIRouter()



@router.get("")
async def report_fall_event(db: AsyncSession = Depends(get_db)):
    try:
        logger.info(f"======== Fall Dectected =========")
        # TODO: wire up real user + organization context when this endpoint is fully implemented
        emergency_number_result = await db.execute(
            select(EmergencyNumber).where(EmergencyNumber.type == EmergencyNumberTypeEnum.emergency_call)
        )
        emergency_number_record = emergency_number_result.scalars().first()
        emergency_phone = emergency_number_record.phone_number if emergency_number_record else None
        user = {
            'first_name': 'Karim',
            'phone_number': emergency_phone,
            'caretaker_name': 'Anna'
        }

        await make_fall_detection_call(user)
        return {"message": "Fall event reporting - to be implemented"} 
    except Exception as e:
        logger.info(f'Fall detection endpoint failed')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error occurred while creating question"
        )
