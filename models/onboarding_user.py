from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Time, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from core.database import Base


class OnboardingUser(Base):
    """Onboarding User model."""

    __tablename__ = "onboarding_users"
    
    #Main
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True, unique=False) 
    phone_number = Column(String(20), index=True, nullable=False, unique=False)
    # age = Column(Integer, nullable=True)
    language=Column(String(50), nullable=True)
    preferred_time=Column(Time, nullable=True)
    timezone=Column(String(30), nullable=True)
    preferred_communication_channel=Column(String(20), nullable=True)
    email_reports=Column(Boolean, default=False)
    whatsapp_reports=Column(Boolean, default=False)
    onboarding_status = Column(Boolean, default=False)
    onboarded_at = Column(DateTime(timezone=True), nullable=True)
    called_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    organization=relationship("Organization", back_populates="onboarding_users")
