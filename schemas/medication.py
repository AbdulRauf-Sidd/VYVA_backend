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
