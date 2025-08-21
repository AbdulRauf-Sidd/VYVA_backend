"""
HealthCare model for health and care records.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class HealthCare(Base):
    """HealthCare model for health and care records."""
    
    __tablename__ = "health_care"
    
    id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # # Vital Signs
    # blood_pressure_systolic = Column(Integer, nullable=True)
    # blood_pressure_diastolic = Column(Integer, nullable=True)
    # heart_rate = Column(Integer, nullable=True)
    # temperature = Column(Float, nullable=True)
    # oxygen_saturation = Column(Integer, nullable=True)
    
    # # Health Metrics
    # blood_glucose = Column(Float, nullable=True)
    # weight = Column(Float, nullable=True)
    # bmi = Column(Float, nullable=True)
    
    # # Symptoms and Notes
    # symptoms = Column(Text, nullable=True)
    # notes = Column(Text, nullable=True)
    # mood = Column(String(50), nullable=True)  # happy, sad, anxious, etc.
    
    # # Medication Compliance
    # medication_taken = Column(Boolean, default=False)
    # medication_notes = Column(Text, nullable=True)
    
    # # Activity and Exercise
    # steps_count = Column(Integer, nullable=True)
    # exercise_minutes = Column(Integer, nullable=True)
    # activity_type = Column(String(100), nullable=True)
    
    # # Sleep
    # sleep_hours = Column(Float, nullable=True)
    # sleep_quality = Column(String(50), nullable=True)  # poor, fair, good, excellent
    
    # # Timestamps
    # recorded_at = Column(DateTime(timezone=True), server_default=func.now())
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # # Relationships
    # user = relationship("User", back_populates="health_care_records")
    
    # def __repr__(self):
    #     return f"<HealthCare(id={self.id}, user_id={self.user_id}, recorded_at={self.recorded_at})>" 