from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from zoneinfo import ZoneInfo
from sqlalchemy.orm import relationship

from core.database import Base


class Organization(Base):
    __tablename__ = "organizations"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    country = Column(String(50), nullable=False)
    timezone = Column(String(20), nullable=False, default="UTC")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    onboarding_agent_id = Column(String(100), nullable=False)
    users = relationship("User", back_populates="organization")
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}')>"

def to_local_time(dt: datetime, tz_name: str) -> datetime:
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(ZoneInfo(tz_name))