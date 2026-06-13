from enum import Enum as PyEnum
from pydantic import BaseModel
from typing import Optional, List
from datetime import time, date, datetime

class MedicationTimeBase(BaseModel):
    time_of_day: time
    notes: Optional[str] = None

class MedicationTimeCreate(MedicationTimeBase):
    pass

class MedicationTimeInDB(MedicationTimeBase):
    id: int
    medication_id: int
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class MedicationBase(BaseModel):
    name: str
    dosage: str
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    purpose: Optional[str] = None
    side_effects: Optional[str] = None
    notes: Optional[str] = None
    

class MedicationCreate(MedicationBase):
    user_id: int
    times_of_day: List[MedicationTimeCreate] = []

class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    purpose: Optional[str] = None
    side_effects: Optional[str] = None
    notes: Optional[str] = None

class MedicationInDB(MedicationBase):
    id: int
    user_id: int
    times_of_day: List[str] = [] 
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

# For your input format
class MedicationInput(BaseModel):
    name: str
    dosage: str
    times: List[str]  # Accept string times like "09:00"
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    purpose: Optional[str] = None

class BulkMedicationRequest(BaseModel):
    medication_details: List[MedicationInput]
    user_id: Optional[int] = None
    name: Optional[str] = None
    channel: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    caretaker_alerts: Optional[bool] = None
    caretaker_channel: Optional[str] = None
    caretaker_email: Optional[str] = None
    caretaker_phone: Optional[str] = None
    caretaker_name: Optional[str] = None


class BulkMedicationSchema(BaseModel):
    medication_details: List[MedicationInput]
    user_id: int = None


class WeeklyScheduleRequest(BaseModel):
    user_id: int
    date_start: date
    date_end: date
    is_present: bool


class MedicationLogItem(BaseModel):
    medication_id: int
    time_id: int
    taken: bool

class MedicationLogRequest(BaseModel):
    user_id: int
    medication_logs: List[MedicationLogItem]
    reminder: bool = False
    reminder_time: Optional[time] = None


class MedicationSlotInput(BaseModel):
    time: str  # HH:MM 24-hour format
    days: Optional[List[str]] = None

class MedicationCreateRequest(BaseModel):
    name: str
    dosage: str
    purpose: Optional[str] = None
    medication_slot: List[MedicationSlotInput]

class MedicationUpdateRequest(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    purpose: Optional[str] = None
    medication_slot: Optional[List[MedicationSlotInput]] = None

class MedicationTimeDetail(BaseModel):
    id: int
    medication_id: int
    time: str
    days: Optional[List[str]] = None

class MedicationDetail(BaseModel):
    id: int
    name: str
    dosage: str
    purpose: Optional[str] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    times: List[MedicationTimeDetail]


class CheckinLogStatusEnum(str, PyEnum):
    unconfirmed = "unconfirmed"
    reported_okay = "reported_okay"
    reported_issue = "reported_issue"

class UpdateCheckinLogRequest(BaseModel):
    status: CheckinLogStatusEnum

class CheckinLogResponse(BaseModel):
    id: int
    checkin_id: Optional[int] = None
    status: str
    date: datetime


class ScheduledItem(BaseModel):
    type: str        # "medication" | "check_up_call" | "brain_coach" | "general_reminder"
    time: str        # HH:MM in user's local timezone
    details: dict    # type-specific fields

class TodayScheduleResponse(BaseModel):
    items: List[ScheduledItem]