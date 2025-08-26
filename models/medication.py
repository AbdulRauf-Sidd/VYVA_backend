"""
Medication model for medication management.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


from enum import Enum

# class LongTermConditionEnum(str, Enum):
#     DIABETES = "Diabetes"
#     HEART_DISEASE = "Heart Disease"
#     HYPERTENSION = "Hypertension"
#     HIGH_CHOLESTEROL = "High Cholesterol"
#     STROKE = "Stroke"
#     ARTHRITIS = "Arthritis"
#     OSTEOPOROSIS = "Osteoporosis"
#     RESPIRATORY_DISEASE = "Respiratory Disease"
#     CANCER = "Cancer"
#     KIDNEY_DISEASE = "Kidney Disease"
#     LIVER_DISEASE = "Liver Disease"
#     ALZHEIMERS = "Alzheimer’s"
#     DEMENTIA = "Dementia"
#     PARKINSONS = "Parkinson’s"
#     ANXIETY = "Anxiety"
#     DEPRESSION = "Depression"
#     VISION_PROBLEMS = "Vision Problems"
#     HEARING_LOSS = "Hearing Loss"
#     CHRONIC_PAIN = "Chronic Pain"
#     MOBILITY_IMPAIRMENT = "Mobility Impairment"
#     OTHER = "Other"


# class LongTermCondition(Base):
#     __tablename__ = "long_term_conditions"

#     id = Column(Integer, primary_key=True, index=True)
#     name = Column(SQLEnum(LongTermConditionEnum), unique=True, nullable=False)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    

class Medication(Base):
    """Medication model for medication management."""
    
    __tablename__ = "medications"
    
    id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # # Medication Information
    # name = Column(String(255), nullable=False)
    # generic_name = Column(String(255), nullable=True)
    # dosage = Column(String(100), nullable=False)  # e.g., "10mg", "1 tablet"
    # frequency = Column(String(100), nullable=False)  # e.g., "twice daily", "every 8 hours"
    # instructions = Column(Text, nullable=True)  # e.g., "Take with food"
    
    # # Prescription Details
    # prescribed_by = Column(String(255), nullable=True)
    # prescription_date = Column(DateTime, nullable=True)
    # refill_date = Column(DateTime, nullable=True)
    # quantity = Column(Integer, nullable=True)
    # remaining_pills = Column(Integer, nullable=True)
    
    # # Timing
    # morning_dose = Column(Boolean, default=False)
    # afternoon_dose = Column(Boolean, default=False)
    # evening_dose = Column(Boolean, default=False)
    # bedtime_dose = Column(Boolean, default=False)
    
    # # Custom times (for specific medication schedules)
    # custom_times = Column(Text, nullable=True)  # JSON array of times
    
    # # Status
    # is_active = Column(Boolean, default=True)
    # is_controlled_substance = Column(Boolean, default=False)
    
    # # Side Effects and Notes
    # side_effects = Column(Text, nullable=True)
    # notes = Column(Text, nullable=True)
    
    # # Timestamps
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # # Relationships
    # user = relationship("User", back_populates="medications")
    
    # def __repr__(self):
    #     return f"<Medication(id={self.id}, name='{self.name}', user_id={self.user_id})>" 