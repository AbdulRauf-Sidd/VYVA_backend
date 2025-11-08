from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, String, Boolean, DateTime, Time, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from models.onboarding_user import OnboardingUser

from core.database import Base


class OnboardingLogs(Base):
    """Onboarding Logs model."""

    __tablename__ = "onboarding_logs"
    
    #Main
    id = Column(Integer, primary_key=True, index=True)
    call_at = Column(DateTime(timezone=True), nullable=True)
    call_id = Column(String(255), nullable=True)
    onboarding_user=relationship("OnboardingUser", back_populates="onboarding_logs")
    onboarding_user_id=Column(Integer, ForeignKey("onboarding_users.id"), nullable=True)
    summary = Column(String(1000), nullable=True)

