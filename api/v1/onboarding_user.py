from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User
from models.onboarding_user import OnboardingUser
from datetime import datetime
from sqlalchemy.sql import func
from core.database import get_db
from services.email_service import email_service
import logging
from schemas.onboarding_user import OnboardingRequestBody

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new onboarding user",
    description="Create a new onboarding user with the provided details"
)
async def onboard_user(
    payload: OnboardingRequestBody = Body(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        # onboarding_user_record
        print(payload.model_dump())

        return {
            "status": "success",
            "message": "Payload processed",
            "received": payload.model_dump()
        }
    except Exception as e:
        logger.error(f"Error processing payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    