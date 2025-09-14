"""
Medication model for medication management.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Time
from datetime import datetime


from core.database import Base


from enum import Enum

class Medication(Base):
    """Medication model for medication management."""
    
    __tablename__ = "medications"
    
    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Medication Information
    name = Column(String(255), nullable=False)
    dosage = Column(String(100), nullable=False)  # e.g., "10mg", "1 tablet"
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    purpose = Column(Text, nullable=True)  # e.g., "Blood pressure control"
    side_effects = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    user = relationship("User", back_populates="medications")
    times_of_day = relationship("MedicationTime", back_populates="medication", cascade="all, delete-orphan")


class MedicationTime(Base):
    """Medication time model for tracking when medications should be taken."""
    
    __tablename__ = "medication_times"
    
    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    time_of_day = Column(Time, nullable=True) 
    notes = Column(String(150), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    medication = relationship("Medication", back_populates="times_of_day")
