"""
Symptom Checker Response Model

Database model for storing symptom analysis responses.
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from core.database import Base


class SymptomCheckerResponse(Base):
    """Model for storing symptom checker analysis responses."""
    
    __tablename__ = "symptom_checker_responses"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(64), unique=True, index=True, nullable=False)
    
    # Input data
    symptoms = Column(Text, nullable=False)
    full_name = Column(String(255), nullable=True)
    language = Column(String(10), nullable=True)
    model_type = Column(String(50), nullable=True)
    followup_count = Column(Integer, nullable=True)
    # Enhanced symptom data
    heart_rate = Column(String(20), nullable=True)
    severity_scale = Column(String(20), nullable=True)
    duration = Column(String(100), nullable=True)
    respiratory_rate = Column(String(20), nullable=True)
    additional_notes = Column(Text, nullable=True)
    
    # Response data
    email = Column(Text, nullable=True)  # Full response with HTML
    summary = Column(Text, nullable=True)  # Clean summary
    breakdown = Column(JSON, nullable=True)  # Structured breakdown
    severity = Column(String(20), nullable=True)  # severe/mild
    is_emergency = Column(Boolean, nullable=False, default=False)
    status = Column(String(20), nullable=False, default="success")
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    def __repr__(self):
        return f"<SymptomCheckerResponse(id={self.id}, conversation_id='{self.conversation_id}', severity='{self.severity}')>"
