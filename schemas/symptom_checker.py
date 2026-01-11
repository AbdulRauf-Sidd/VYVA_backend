"""
Symptom Checker Schemas

Pydantic models for symptom checker interactions, vitals data, and caregiver dashboard.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime


class VitalsData(BaseModel):
    """Structured model for vitals data."""
    
    heart_rate: Optional[Dict[str, Any]] = Field(
        None,
        description="Heart rate data with value, unit, and optional confidence/timestamp"
    )
    respiratory_rate: Optional[Dict[str, Any]] = Field(
        None,
        description="Respiratory rate data with value, unit, and optional confidence/timestamp"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "heart_rate": {
                    "value": 72,
                    "unit": "bpm",
                    "confidence": 0.95,
                    "timestamp": "2025-01-20T10:30:00Z"
                },
                "respiratory_rate": {
                    "value": 16,
                    "unit": "breaths/min",
                    "confidence": 0.92,
                    "timestamp": "2025-01-20T10:30:00Z"
                }
            }
        }
    }


class SymptomCheckerInteractionCreate(BaseModel):
    """Schema for creating a new symptom checker interaction from ElevenLabs webhook."""
    
    user_id: Optional[int] = Field(None, description="User ID from dynamic variables")
    conversation_id: str = Field(..., description="Unique conversation/call identifier")
    call_duration_secs: Optional[int] = Field(None, description="Call duration in seconds")
    call_timestamp: Optional[datetime] = Field(None, description="When the call occurred")
    vitals_data: Optional[Dict[str, Any]] = Field(None, description="Structured vitals data (JSON)")
    vitals_ai_summary: Optional[str] = Field(None, description="AI-generated summary of vitals")
    symptoms_ai_summary: Optional[str] = Field(None, description="AI-generated summary of symptoms")
    symptoms: Optional[str] = Field(None, description="Symptoms description or transcript")
    heart_rate: Optional[str] = Field(None, description="Heart rate captured during call")
    respiratory_rate: Optional[str] = Field(None, description="Respiratory rate captured during call")
    status: Optional[str] = Field("success", description="Status of the interaction")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 123,
                "conversation_id": "call_abc123",
                "call_duration_secs": 180,
                "call_timestamp": "2025-01-20T10:30:00Z",
                "vitals_data": {
                    "heart_rate": {"value": 72, "unit": "bpm"},
                    "respiratory_rate": {"value": 16, "unit": "breaths/min"}
                },
                "vitals_ai_summary": "Heart rate and respiratory rate are within normal ranges.",
                "symptoms_ai_summary": "Patient reports mild headache and fatigue.",
                "heart_rate": "72",
                "respiratory_rate": "16"
            }
        }
    }


class SymptomCheckerInteractionRead(BaseModel):
    """Schema for reading symptom checker interaction data."""
    
    id: int
    user_id: Optional[int] = None
    conversation_id: str
    call_duration_secs: Optional[int] = None
    call_timestamp: Optional[datetime] = None
    vitals_data: Optional[Dict[str, Any]] = None
    vitals_ai_summary: Optional[str] = None
    symptoms_ai_summary: Optional[str] = None
    
    # Existing fields from SymptomCheckerResponse model
    heart_rate: Optional[str] = None
    respiratory_rate: Optional[str] = None
    symptoms: Optional[str] = None
    full_name: Optional[str] = None
    language: Optional[str] = None
    severity: Optional[str] = None
    is_emergency: bool = False
    status: str = "success"
    created_at: datetime
    updated_at: Optional[datetime] = None
    
    model_config = {
        "from_attributes": True,
        "json_schema_extra": {
            "example": {
                "id": 1,
                "user_id": 123,
                "conversation_id": "call_abc123",
                "call_duration_secs": 180,
                "call_timestamp": "2025-01-20T10:30:00Z",
                "vitals_data": {
                    "heart_rate": {"value": 72, "unit": "bpm"},
                    "respiratory_rate": {"value": 16, "unit": "breaths/min"}
                },
                "vitals_ai_summary": "Heart rate and respiratory rate are within normal ranges.",
                "symptoms_ai_summary": "Patient reports mild headache and fatigue.",
                "heart_rate": "72",
                "respiratory_rate": "16",
                "symptoms": "Headache, fatigue",
                "full_name": "John Doe",
                "language": "en",
                "severity": "mild",
                "is_emergency": False,
                "status": "success",
                "created_at": "2025-01-20T10:30:00Z",
                "updated_at": "2025-01-20T10:30:00Z"
            }
        }
    }


class SymptomCheckerListResponse(BaseModel):
    """Schema for paginated list of symptom checker interactions."""
    
    items: List[SymptomCheckerInteractionRead]
    total: int = Field(..., description="Total number of interactions")
    page: int = Field(1, ge=1, description="Current page number")
    page_size: int = Field(10, ge=1, le=100, description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 10,
                "total_pages": 0
            }
        }
    }


class CaregiverDashboardResponse(BaseModel):
    """Schema for aggregated caregiver dashboard view."""
    
    total_interactions: int = Field(..., description="Total number of interactions")
    recent_interactions: List[SymptomCheckerInteractionRead] = Field(
        default_factory=list,
        description="Most recent interactions (e.g., last 5)"
    )
    emergency_count: int = Field(0, description="Number of emergency cases")
    average_heart_rate: Optional[float] = Field(None, description="Average heart rate across interactions")
    average_respiratory_rate: Optional[float] = Field(None, description="Average respiratory rate across interactions")
    last_interaction_date: Optional[datetime] = Field(None, description="Date of most recent interaction")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "total_interactions": 25,
                "recent_interactions": [],
                "emergency_count": 2,
                "average_heart_rate": 72.5,
                "average_respiratory_rate": 16.2,
                "last_interaction_date": "2025-01-20T10:30:00Z"
            }
        }
    }


class VitalsHistoryResponse(BaseModel):
    """Schema for vitals history time-series data."""
    
    user_id: int
    vitals_records: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of vitals measurements with timestamps"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "user_id": 123,
                "vitals_records": [
                    {
                        "timestamp": "2025-01-20T10:30:00Z",
                        "heart_rate": {"value": 72, "unit": "bpm"},
                        "respiratory_rate": {"value": 16, "unit": "breaths/min"}
                    }
                ]
            }
        }
    }

