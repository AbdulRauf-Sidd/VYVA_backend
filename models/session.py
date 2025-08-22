from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum

from core.database import Base


class UserCallSessions(Base):
    """Model for tracking user call sessions."""

    __tablename__ = "user_call_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # Links to the User model
    call_id = Column(String(255), nullable=False)  # Unique identifier for the call
    source = Column(String(50), nullable=True)  # Source of the call (e.g., "Mobile", "Web", "Telehealth")
    status = Column(String(50), nullable=True)  # Status of the call (e.g., "Completed", "Missed", "voicemail")
    summary = Column(Text, nullable=True)  # Summary or notes about the call
    date = Column(DateTime(timezone=True), server_default=func.now())  # Date and time of the call
    agent = Column(String(50), nullable=True)  # Agent who handled the call    