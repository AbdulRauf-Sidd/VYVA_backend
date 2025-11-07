from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum as SQLEnum
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
    email = Column(String(255), index=True, nullable=True, unique=True) 
    phone_number = Column(String(20), nullable=True, unique=True)
    age = Column(Integer, nullable=True)
    onboarding_status = Column(Boolean, default=False)
    onboarded_at = Column(DateTime(timezone=True), nullable=True)
    called_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
