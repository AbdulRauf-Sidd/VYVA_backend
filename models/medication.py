"""
Medication model for medication management.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


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