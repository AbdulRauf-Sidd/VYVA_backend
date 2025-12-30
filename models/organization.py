from datetime import date, datetime, time, timedelta
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from zoneinfo import ZoneInfo
from sqlalchemy.orm import relationship
from sqlalchemy import event
from slugify import slugify
from enum import Enum as PyEnum

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
    onboarding_users = relationship("OnboardingUser", back_populates="organization")
    sub_domain = Column(String(100), nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}')>"  

class AgentTypeEnum(str, PyEnum):
    MEDICATION_MANAGER = "medication_manager"
    MAIN_AGENT = "main_agent"
    SYMPTOM_CHECKER = "symptom_checker"
    BRAIN_COACH = "brain_coach"
    ONBOARDING_AGENT = "onboarding_agent"
    MEDICATION_REMINDER = "medication_reminder"
    FALL_DETECTOR = "fall_detector"

class OrganizationAgents(Base):
    __tablename__ = "organization_agents"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    agent_id = Column(String(255), nullable=False)
    agent_type = Column(SQLEnum(AgentTypeEnum), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="agents")
    name_slug = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<OrganizationAgents(id={self.id}, name='{self.name}')>"
    

@event.listens_for(OrganizationAgents, "before_insert")
def before_insert(mapper, connection, target):
    if target.name and not target.name_slug:
        target.name_slug = slugify(target.name)