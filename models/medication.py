"""
Medication model for medication management.
"""

import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float, Enum as SQLEnum, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from sqlalchemy import Time
from datetime import datetime, timezone
from sqlalchemy.dialects.postgresql import ENUM as PGEnum

from core.database import Base

class Medication(Base):
    """Medication model for medication management."""
    
    __tablename__ = "medications"
    
    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Medication Information
    name = Column(String(255), nullable=False)
    dosage = Column(String(100), nullable=False)  # e.g., "10mg", "1 tablet"
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    purpose = Column(Text, nullable=True)  # e.g., "Blood pressure control"
    side_effects = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    is_active = Column(Boolean, nullable=True, default=True)

    # Relationships
    user = relationship("User", back_populates="medications")
    times_of_day = relationship("MedicationTime", back_populates="medication", cascade="all, delete-orphan", passive_deletes=True, lazy="selectin")
    logs = relationship(
        "MedicationLog",
        back_populates="medication",
        cascade="all, delete-orphan",
        passive_deletes=True
    )

    def __repr__(self):
        return f"<Medication(id={self.id}, name={self.name}>"

class MedicationTime(Base):
    """Medication time model for tracking when medications should be taken."""
    
    __tablename__ = "medication_times"
    
    id = Column(Integer, primary_key=True, index=True)
    medication_id = Column(Integer, ForeignKey("medications.id", ondelete="CASCADE"), nullable=False)
    time_of_day = Column(Time, nullable=True) 
    notes = Column(String(150), nullable=True)
    created_at = Column(DateTime, default=datetime.now())
    updated_at = Column(DateTime, default=datetime.now(), onupdate=datetime.now())

    # Relationships
    medication = relationship("Medication", back_populates="times_of_day")

    logs = relationship(
        "MedicationLog",
        back_populates="medication_time",
        cascade="all, delete-orphan",
        passive_deletes=True
    )
    
    def __repr__(self):
        return f"<MedicationTime(id={self.id}, medication_id={self.medication_id}, time_of_day={self.time_of_day})>"


class MedicationStatus(enum.Enum):
    taken = "taken"
    missed = "missed"
    unconfirmed = "unconfirmed"
    upcoming = "upcoming"


class MedicationLog(Base):
    __tablename__ = "medication_logs"

    id = Column(Integer, primary_key=True, index=True)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    medication_id = Column(
        Integer,
        ForeignKey("medications.id", ondelete="CASCADE"),
        nullable=False
    )

    medication_time_id = Column(
        Integer,
        ForeignKey("medication_times.id", ondelete="CASCADE"),
        nullable=True
    )

    taken_at = Column(DateTime(timezone=True), nullable=True)

    status = Column(String(50), nullable=False)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    medication = relationship("Medication", back_populates="logs")
    medication_time = relationship("MedicationTime", back_populates="logs")
    user = relationship("User", back_populates="medication_logs")