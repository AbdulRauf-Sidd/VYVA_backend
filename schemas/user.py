from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, EmailStr
from enum import Enum
from .health_care import LongTermConditionBase, LongTermConditionCreate, LongTermConditionRead
from .activities import TopicOfInterestBase, TopicOfInterestCreate, TopicOfInterestRead, ActivityBase, ActivityCreate, ActivityRead

# Import the same enums from your model
class LivingSituation(str, Enum):
    ALONE = "Alone"
    WITH_PARTNER = "With Partner"
    WITH_FAMILY = "With Family"

class MobilityEnum(str, Enum):
    INDEPENDENT = "Independent"
    WALK_WITH_ASSISTANCE = "Walk with assistance"
    WHEELCHAIR = "Wheelchair"
    BED_BOUND = "Bed-bound"

class PreferredDoctorTypeEnum(str, Enum):
    MY_OWN = "My own"
    ANY_AVAILABLE = "Any available"
    SPECIALIST = "Specialist"

class PreferredConsultationTypeEnum(str, Enum):
    PHONE = "Phone"
    VIDEO = "Video"

class PreferredConsultationLanguageEnum(str, Enum):
    ENGLISH = "English"
    SPANISH = "Spanish"
    GERMAN = "German"
    FRENCH = "French"
    OTHER = "Other"

class BrainCoachTimeEnum(str, Enum):
    MORNING = "Morning"
    AFTERNOON = "Afternoon"
    EVENING = "Evening"

class BrainCoachComplexityEnum(str, Enum):
    EASY = "Easy"
    MEDIUM = "Medium"
    ADVANCED = "Advanced"
    PROGRESSIVE = "Progressive"

class RegularSafetyCheckInsEnum(str, Enum):
    DAILY = "Daily"
    TWICE_DAILY = "Twice Daily"

class FaithTraditionEnum(str, Enum):
    CHRISTIANITY = "Christianity"
    ISLAM = "Islam"
    JUDAISM = "Judaism"
    HINDUISM = "Hinduism"
    BUDDHISM = "Buddhism"
    OTHER = "Other"
    PREFER_NOT_TO_SAY = "Prefer not to say"

class PreferredCheckInTimeEnum(str, Enum):
    EARLY_MORNING = "Early Morning (6–9 AM)"
    LATE_MORNING = "Late Morning"
    EARLY_AFTERNOON = "Early Afternoon"
    LATE_AFTERNOON = "Late Afternoon"
    EVENING = "Evening"
    NIGHT = "Night"

class CheckInFrequencyEnum(str, Enum):
    MULTIPLE_PER_DAY = "Multiple per day"
    DAILY = "Daily"
    SEVERAL_PER_WEEK = "Several per week"
    WEEKLY = "Weekly"
    EMERGENCIES_ONLY = "Emergencies only"
    WEEKENDS_ONLY = "Weekends only"
    HOLIDAYS = "Holidays/special occasions"



# Main User schemas
class UserBase(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    age: Optional[int] = None
    living_situation: Optional[LivingSituation] = None
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    # Health and Care
    social_check_ins: Optional[bool] = None
    faith_tradition: Optional[FaithTraditionEnum] = None
    local_event_recommendations: Optional[bool] = None
    preferred_check_in_time: Optional[PreferredCheckInTimeEnum] = None
    check_in_frequency: Optional[CheckInFrequencyEnum] = None
    # Medications
    wants_caretaker_alerts: Optional[bool] = None
    wants_reminders: Optional[bool] = None
    takes_medication: Optional[bool] = None
    preferred_channel: Optional[str] = None
    missed_dose_alerts: Optional[bool] = None
    escalate_to_emergency_contact: Optional[bool] = None
    medical_devices: Optional[str] = None
    mobility: Optional[MobilityEnum] = None
    telehealth_activation: Optional[bool] = None
    preferred_doctor_type: Optional[PreferredDoctorTypeEnum] = None
    preferred_consultation_type: Optional[PreferredConsultationTypeEnum] = None
    preferred_consultation_language: Optional[PreferredConsultationLanguageEnum] = None
    # Brain Coach
    brain_coach_activation: Optional[bool] = None
    brain_coach_time: Optional[BrainCoachTimeEnum] = None
    brain_coach_complexity: Optional[BrainCoachComplexityEnum] = None
    performance_reports: Optional[bool] = None
    cognitive_decline_alerts: Optional[bool] = None
    # Fall Detection
    fall_detection_activation: Optional[bool] = None
    fall_auto_alert_to_caregiver: Optional[bool] = None
    regular_safety_check_ins: Optional[RegularSafetyCheckInsEnum] = None
    # Doctor and Pharmacy
    primary_doctor_name: Optional[str] = None
    primary_doctor_phone: Optional[str] = None
    preferred_pharmacy_name: Optional[str] = None
    preferred_pharmacy_phone: Optional[str] = None
    preferred_hospital_name: Optional[str] = None
    preferred_hospital_phone: Optional[str] = None
    # Device Notifications
    device_token: Optional[str] = None
    expiration: Optional[str] = None
    p256dh: Optional[str] = None
    auth: Optional[str] = None

    #Caretaker Information
    caretaker_preferred_channel: Optional[str] = None  # e.g., "email", "sms", "push"
    caretaker_email: Optional[str] = None
    caretaker_phone_number: Optional[str] = None

class UserCreate(UserBase):
    pass

class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    email: Optional[str] = None
    age: Optional[int] = None
    living_situation: Optional[LivingSituation] = None
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    # Health and Care
    social_check_ins: Optional[bool] = None
    faith_tradition: Optional[FaithTraditionEnum] = None
    local_event_recommendations: Optional[bool] = None
    preferred_check_in_time: Optional[PreferredCheckInTimeEnum] = None
    check_in_frequency: Optional[CheckInFrequencyEnum] = None
    # Medications
    wants_caretaker_alerts: Optional[bool] = None
    wants_reminders: Optional[bool] = None
    takes_medication: Optional[bool] = None
    missed_dose_alerts: Optional[bool] = None
    escalate_to_emergency_contact: Optional[bool] = None
    medical_devices: Optional[str] = None
    mobility: Optional[MobilityEnum] = None
    telehealth_activation: Optional[bool] = None
    preferred_doctor_type: Optional[PreferredDoctorTypeEnum] = None
    preferred_consultation_type: Optional[PreferredConsultationTypeEnum] = None
    preferred_consultation_language: Optional[PreferredConsultationLanguageEnum] = None
    # Brain Coach
    brain_coach_activation: Optional[bool] = None
    brain_coach_time: Optional[BrainCoachTimeEnum] = None
    brain_coach_complexity: Optional[BrainCoachComplexityEnum] = None
    performance_reports: Optional[bool] = None
    cognitive_decline_alerts: Optional[bool] = None
    # Fall Detection
    fall_detection_activation: Optional[bool] = None
    fall_auto_alert_to_caregiver: Optional[bool] = None
    regular_safety_check_ins: Optional[RegularSafetyCheckInsEnum] = None
    # Doctor and Pharmacy
    primary_doctor_name: Optional[str] = None
    primary_doctor_phone: Optional[str] = None
    preferred_pharmacy_name: Optional[str] = None
    preferred_pharmacy_phone: Optional[str] = None
    preferred_hospital_name: Optional[str] = None
    preferred_hospital_phone: Optional[str] = None
    # Device Notifications
    device_token: Optional[str] = None
    expiration: Optional[str] = None
    p256dh: Optional[str] = None
    auth: Optional[str] = None

class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    # Health and Care
    social_check_ins: Optional[bool] = None
    faith_tradition: Optional[FaithTraditionEnum] = None
    local_event_recommendations: Optional[bool] = None
    preferred_check_in_time: Optional[PreferredCheckInTimeEnum] = None
    check_in_frequency: Optional[CheckInFrequencyEnum] = None
    # Medications
    wants_caretaker_alerts: Optional[bool] = None
    wants_reminders: Optional[bool] = None
    takes_medication: Optional[bool] = None
    missed_dose_alerts: Optional[bool] = None
    escalate_to_emergency_contact: Optional[bool] = None
    medical_devices: Optional[str] = None
    mobility: Optional[MobilityEnum] = None
    telehealth_activation: Optional[bool] = None
    preferred_doctor_type: Optional[PreferredDoctorTypeEnum] = None
    preferred_consultation_type: Optional[PreferredConsultationTypeEnum] = None
    preferred_consultation_language: Optional[PreferredConsultationLanguageEnum] = None
    # Brain Coach
    brain_coach_activation: Optional[bool] = None
    brain_coach_time: Optional[BrainCoachTimeEnum] = None
    brain_coach_complexity: Optional[BrainCoachComplexityEnum] = None
    performance_reports: Optional[bool] = None
    cognitive_decline_alerts: Optional[bool] = None
    # Fall Detection
    fall_detection_activation: Optional[bool] = None
    fall_auto_alert_to_caregiver: Optional[bool] = None
    regular_safety_check_ins: Optional[RegularSafetyCheckInsEnum] = None
    # Doctor and Pharmacy
    primary_doctor_name: Optional[str] = None
    primary_doctor_phone: Optional[str] = None
    preferred_pharmacy_name: Optional[str] = None
    preferred_pharmacy_phone: Optional[str] = None
    preferred_hospital_name: Optional[str] = None
    preferred_hospital_phone: Optional[str] = None
    # Device Notifications
    device_token: Optional[str] = None
    expiration: Optional[str] = None
    p256dh: Optional[str] = None
    auth: Optional[str] = None
    # Relationships
    long_term_conditions: List[LongTermConditionRead] = []
    topics_of_interest: List[TopicOfInterestRead] = []
    preferred_activities: List[ActivityRead] = []
    
    model_config = ConfigDict(from_attributes=True)

    @property
    def full_name(self) -> str:
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.email