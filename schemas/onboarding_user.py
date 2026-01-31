from schemas.user import UserBase
from typing import List, Optional
from datetime import datetime, date
from pydantic import BaseModel


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

class MedicationDetailsItem(BaseModel):
    end_date: Optional[date] = None
    name: str
    purpose: Optional[str] = None
    side_effects: Optional[str] = None
    dosage: str
    start_date: Optional[date] = None
    times: List[str]


class CheckInDetails(BaseModel):
    wants_check_ins: bool
    frequency_in_days: Optional[int] = None


class BrainCoach(BaseModel):
    wants_brain_coach_sessions: bool
    frequency_in_days: Optional[int] = None 


class OnboardingRequestBody(BaseModel):
    user_id: int
    medication_details: Optional[List[MedicationDetailsItem]] = None
    caretaker_phone: Optional[str] = None
    check_in_details: Optional[CheckInDetails] = None
    caretaker_name: Optional[str] = None
    brain_coach: Optional[BrainCoach] = None
    caretaker_consent: Optional[bool] = None
    health_conditions: Optional[List[str]] = None
    address: Optional[str] = None
    mobility: Optional[List[str]] = None
    preferences: Optional[List[str]] = None
    preferred_reminder_channel: Optional[str] = None
    preferred_reports_channel: Optional[str] = None
