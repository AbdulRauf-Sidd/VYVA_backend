from pydantic import RootModel, BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime
from datetime import time
from pydantic import field_validator
class StandardSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None

class SessionCheckResponse(BaseModel):
    success: bool = True
    user_id: int
    first_name: Optional[str] = None

class SessionSuccessResponse(BaseModel):
    success: bool = True
    message: str
    session_id: Optional[str] = None

class StandardErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[str] = None
    
class LogEntry(BaseModel):
    taken_at: Optional[datetime] = None
    status: Optional[str] = None

class MedicationEntry(BaseModel):
    medication_name: str
    time: str
    log: Optional[LogEntry] = None
class WeeklyScheduleResponse(RootModel):
    root: dict[str, list[MedicationEntry]]
    
class MedicationTimeOut(BaseModel):
    id: int
    time_of_day: Optional[time]
    notes: Optional[str]

    class Config:
        from_attributes = True


class MedicationOut(BaseModel):
    id: int
    name: str
    dosage: str
    purpose: str
    side_effects: Optional[str]
    notes: Optional[str]
    times_of_day: List[MedicationTimeOut]

    @field_validator("purpose", mode="before")
    def default_purpose(cls, v):
        return v or "N/A"

    class Config:
        from_attributes = True