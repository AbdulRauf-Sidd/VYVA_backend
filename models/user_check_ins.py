from sqlalchemy import Column, ForeignKey, Integer, String, DateTime, Boolean, Time, Enum
from sqlalchemy.sql import func
from zoneinfo import ZoneInfo
from sqlalchemy.orm import relationship
import enum

from core.database import Base

class CheckInType(enum.Enum):
    BRAIN_COACH = "brain_coach"
    CHECK_UP_CALL = "check_up_call"

class UserCheckin(Base):
    __tablename__ = "user_checkins"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="user_checkins")
    scheduled_sessions = relationship("ScheduledSession", back_populates="user_checkin", cascade="all, delete-orphan")
    check_in_type = Column(Enum(CheckInType), nullable=False) # brain coach, check up call. 
    check_in_frequency_days = Column(Integer, nullable=False)
    check_in_time = Column(Time, nullable=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<UserCheckin(id={self.id}, check_in_type='{self.check_in_type}')>"  
    


class ScheduledSession(Base):
    __tablename__ = "scheduled_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    # user = relationship("User", back_populates="scheduled_sessions")
    session_type = Column(Enum(CheckInType), nullable=False)
    scheduled_at = Column(DateTime(timezone=True), nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    is_completed = Column(Boolean, default=False)
    
    user_checkin = relationship("UserCheckin", back_populates="scheduled_sessions")
    user_checkin_id = Column(Integer, ForeignKey("user_checkins.id"), nullable=False)
    
    def __repr__(self):
        return f"<ScheduledSession(id={self.id}, scheduled_at='{self.scheduled_at}', is_completed={self.is_completed})>"