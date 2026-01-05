from pydantic import RootModel, BaseModel
from typing import Optional, Any, Dict, List
from datetime import datetime

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