from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User
from models.onboarding_user import OnboardingUser

from core.database import get_db
from services.email_service import email_service
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "/",
    status_code=status.HTTP_201_CREATED,
    summary="Create a new onboarding user",
    description="Create a new onboarding user with the provided details"
)
async def onboard_user(
    user_id: int = Body(...),
    language: str = Body(None),
    address: str = Body(None),
    emergency_contact_name: str = Body(None),
    emergency_contact_phone: str = Body(None),
    health_conditions: str = Body(None),
    mobility: str = Body(None),
    medication: bool = Body(None),
    brain_coach: bool = Body(None),
    nutrition: bool = Body(None),
    concierge_services: bool = Body(None),
    scam_protection: bool = Body(None),
    email: str = Body(None),
    db: AsyncSession = Depends(get_db)
):

    print("User ID:", user_id)
    print("language:", language)
    print("address:", address)
    print("emergency_contact_name:", emergency_contact_name)
    print("emergency_contact_phone:", emergency_contact_phone)
    print("health_conditions:", health_conditions)
    print("mobility:", mobility)
    print("medication:", medication)
    print("brain_coach:", brain_coach)
    print("nutrition:", nutrition)
    print("concierge_services:", concierge_services)
    print("scam_protection:", scam_protection)
    print("email:", email)

    onboarding_user = await db.get(OnboardingUser, user_id)

    if onboarding_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    user = User(
            id=user_id,
            phone_number=onboarding_user.phone_number,
            land_line=onboarding_user.land_line,
            first_name=onboarding_user.first_name,
            last_name=onboarding_user.last_name,
            organization_id=onboarding_user.organization_id,
            preferred_consultation_language=language,
            street=address,
            emergency_contact_name=emergency_contact_name,
            emergency_contact_phone=emergency_contact_phone,
            health_conditions=health_conditions,
            mobility=mobility,
            takes_medication=medication,
            wants_reminders=medication,
            brain_coach_activation=brain_coach,
            brain_coach_time="Morning" if brain_coach else None,
            nutrition_services_activation=nutrition,
            concierge_services_activation=concierge_services,
            scam_protection_activation=scam_protection,
            email=email
        )
    
    success = await email_service.send_welcome_email(first_name=onboarding_user.first_name, email=email)
    
    db.add(user)
    db.commit()

    if success:
        return {
            "success": True,
            "message": "User onboarded successfully and welcome email sent."
        }
    
    return {
        "success": False,
        "message": "User onboarded successfully but failed to send welcome email."
    }
    

