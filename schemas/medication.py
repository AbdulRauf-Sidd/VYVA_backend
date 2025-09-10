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
    times_of_day: List[MedicationTimeCreate] = []

class MedicationCreate(MedicationBase):
    user_id: int

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
    times_of_day: List[MedicationTimeInDB] = []
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

class BulkMedicationRequest(BaseModel):
    medication_details: List[MedicationInput]
    user_id: int  # Added user_id since it's required
    channel: str
    email: str
    phone: str
    want_caregiver_alerts: bool
    care_giver_channel: Optional[str] = None
    caregiver_email: Optional[str] = None
    caregiver_phone: Optional[str] = None
