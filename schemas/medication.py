from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime, time
from enum import Enum

# MedicationTime Schemas
class MedicationTimeBase(BaseModel):
    time_of_day: Optional[time] = None
    notes: Optional[str] = None

class MedicationTimeCreate(MedicationTimeBase):
    pass

class MedicationTimeUpdate(BaseModel):
    time_of_day: Optional[time] = None
    notes: Optional[str] = None

class MedicationTimeInDB(MedicationTimeBase):
    id: int
    medication_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

# Medication Schemas
class MedicationBase(BaseModel):
    name: str
    dosage: str
    frequency: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    purpose: Optional[str] = None
    side_effects: Optional[str] = None
    notes: Optional[str] = None

    @validator('name', 'dosage', 'frequency')
    def validate_required_fields(cls, v, field):
        if not v or not v.strip():
            raise ValueError(f"{field.name} cannot be empty")
        return v.strip()

    @validator('dosage')
    def validate_dosage_format(cls, v):
        if v and not any(char.isdigit() for char in v):
            raise ValueError("Dosage should contain numeric values (e.g., '10mg', '1 tablet')")
        return v

class MedicationCreate(MedicationBase):
    times_of_day: Optional[List[MedicationTimeCreate]] = None

class MedicationUpdate(BaseModel):
    name: Optional[str] = None
    dosage: Optional[str] = None
    frequency: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    purpose: Optional[str] = None
    side_effects: Optional[str] = None
    notes: Optional[str] = None

    @validator('name', 'dosage', 'frequency', pre=True, always=True)
    def validate_optional_fields(cls, v, field):
        if v is not None:
            if not v or not v.strip():
                raise ValueError(f"{field.name} cannot be empty if provided")
            return v.strip()
        return v

class MedicationInDB(MedicationBase):
    id: int
    user_id: int
    times_of_day: List[MedicationTimeInDB] = []
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True

# Optional: Response schemas for specific endpoints
class MedicationWithTimes(MedicationInDB):
    """Schema for medication with times of day"""
    pass

class MedicationTimeWithMedication(MedicationTimeInDB):
    """Schema for medication time with medication details"""
    medication: Optional[MedicationInDB] = None

    class Config:
        orm_mode = True