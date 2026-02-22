from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, String, Boolean, DateTime, Time, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from models.organization import Organization

from core.database import Base


class OnboardingUser(Base):
    """Onboarding User model."""

    __tablename__ = "onboarding_users"
    
    #Main
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), nullable=True, unique=False) 
    phone_number = Column(String(20), index=True, nullable=False, unique=True)
    address=Column(String(255), nullable=True)
    language=Column(String(50), nullable=True)
    preferred_time=Column(Time, nullable=True)
    timezone=Column(String(30), nullable=True)
    city_state_province=Column(String(100), nullable=True)
    postal_zip_code=Column(String(20), nullable=True)
    caregiver_name=Column(String(100), nullable=True)
    caregiver_contact_number=Column(String(20), nullable=True)
    preferred_communication_channel=Column(String(20), nullable=True)
    onboarding_call_scheduled = Column(Boolean, default=False)
    onboarding_call_task_id = Column(String(255), nullable=True)
    onboarding_status = Column(Boolean, default=False)
    onboarded_at = Column(DateTime(timezone=True), nullable=True)
    call_back_date_time = Column(DateTime(timezone=True), nullable=True)
    consent_given = Column(Boolean, nullable=True)
    call_attempts = Column(Integer, default=0)
    called_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    organization=relationship("Organization", back_populates="onboarding_users")
    organization_id=Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=True)
    onboarding_logs=relationship("OnboardingLogs", back_populates="onboarding_user", cascade="all, delete-orphan", passive_deletes=True)


class OnboardingLogs(Base):
    """Onboarding Logs model."""

    __tablename__ = "onboarding_logs"
    
    #Main
    id = Column(Integer, primary_key=True, index=True)
    call_at = Column(DateTime(timezone=True), nullable=True)
    call_id = Column(String(255), nullable=True)
    onboarding_user=relationship("OnboardingUser", back_populates="onboarding_logs")
    onboarding_user_id=Column(Integer, ForeignKey("onboarding_users.id", ondelete="CASCADE"), nullable=True)
    status=Column(String(50), nullable=True)
    summary = Column(String(1000), nullable=True)

