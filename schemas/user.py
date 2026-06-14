from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from enum import Enum
from .health_care import LongTermConditionRead
from .activities import TopicOfInterestRead, ActivityRead


# Main User schemas
class UserBase(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone_number: Optional[str] = None
    age: Optional[int] = None

class MainUser(UserBase):
    password: Optional[str] = None
    is_primary_landline: Optional[bool] = None
    timezone: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    secondary_phone: Optional[str] = None
    preferred_communication_channel: Optional[str] = None
    preferred_consultation_language: Optional[str] = None
    # Address
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    house_number: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    # Health
    health_conditions: Optional[str] = None
    mobility: Optional[str] = None
    local_event_recommendations: Optional[bool] = None
    # Medications
    wants_caretaker_alerts: Optional[bool] = None
    wants_reminders: Optional[bool] = None
    preferred_reminder_channel: Optional[str] = None
    # Reminders / Reports
    preferred_reports_channel: Optional[str] = None
    # Emergency
    emergency_call_to_caretaker: Optional[bool] = None
    emergency_call_to_government_services: Optional[bool] = None
    emergency_protocol_status: Optional[bool] = None
    # Caretaker
    caretaker_consent: Optional[bool] = None
    # Fall Detection
    fall_detection_activation: Optional[bool] = None
    fall_auto_alert_to_caregiver: Optional[bool] = None
    # Device Notifications
    device_token: Optional[str] = None
    expiration: Optional[str] = None
    p256dh: Optional[str] = None
    auth: Optional[str] = None

class UserUpdate(MainUser):
    pass
    

class UserCreate(MainUser):
    pass

class UserRead(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_primary_landline: Optional[bool] = None
    timezone: Optional[str] = None
    date_of_birth: Optional[datetime] = None
    secondary_phone: Optional[str] = None
    preferred_communication_channel: Optional[str] = None
    preferred_consultation_language: Optional[str] = None
    # Address
    street: Optional[str] = None
    city: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    address: Optional[str] = None
    house_number: Optional[str] = None
    latitude: Optional[str] = None
    longitude: Optional[str] = None
    # Health
    health_conditions: Optional[str] = None
    mobility: Optional[str] = None
    local_event_recommendations: Optional[bool] = None
    # Medications
    wants_caretaker_alerts: Optional[bool] = None
    wants_reminders: Optional[bool] = None
    preferred_reminder_channel: Optional[str] = None
    # Reminders / Reports
    preferred_reports_channel: Optional[str] = None
    # Emergency
    emergency_call_to_caretaker: Optional[bool] = None
    emergency_call_to_government_services: Optional[bool] = None
    emergency_protocol_status: Optional[bool] = None
    # Caretaker
    caretaker_consent: Optional[bool] = None
    # Fall Detection
    fall_detection_activation: Optional[bool] = None
    fall_auto_alert_to_caregiver: Optional[bool] = None
    # Device Notifications
    device_token: Optional[str] = None
    expiration: Optional[str] = None
    p256dh: Optional[str] = None
    auth: Optional[str] = None
    # Relationships
    
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
    

class UpdateFirstTimeAgentsRequest(BaseModel):
    first_time_agents: List[Optional[bool]]


class UpdateSafetySettingsRequest(BaseModel):
    emergency_call_to_caretaker: Optional[bool] = None
    emergency_call_to_government_services: Optional[bool] = None
    emergency_protocol_status: Optional[bool] = None
    fall_detection_activation: Optional[bool] = None
    fall_auto_alert_to_caregiver: Optional[bool] = None


class SafetySettingsResponse(BaseModel):
    emergency_call_to_caretaker: Optional[bool]
    emergency_call_to_government_services: Optional[bool]
    emergency_protocol_status: Optional[bool]
    fall_detection_activation: Optional[bool]
    fall_auto_alert_to_caregiver: Optional[bool]

    model_config = ConfigDict(from_attributes=True)
