from schemas.user import UserBase
from typing import Optional
from datetime import datetime

class OnboardingUserCreate(UserBase):
    pass

class OnboardingUserUpdate(UserBase):
    onboarding_status: Optional[bool] = None
    onboarded_at: Optional[datetime] = None
    called_at: Optional[datetime] = None

class OnboardingUserRead(UserBase):
    onboarding_status: bool
    onboarded_at: Optional[datetime]
    called_at: Optional[datetime]
    created_at: datetime


