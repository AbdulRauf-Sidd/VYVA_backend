from enum import Enum as PyEnum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class PromptTypeEnum(str, PyEnum):
    conversation_plan = "conversation_plan"
    medication_reminder_plan = "medication_reminder_plan"
    brain_coach_plan = "brain_coach_plan"


class UserConversationPlan(Base):
    """Cached conversation plans per user per week, keyed by plan_type."""

    __tablename__ = "user_conversation_plans"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    plan_type = Column(String(50), nullable=False, index=True)
    plan = Column(JSON, nullable=False)
    dynamic_variable = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    user = relationship("User")


class Prompt(Base):
    __tablename__ = "prompts"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(120), nullable=False)
    prompt_type = Column(String(50), nullable=False, index=True)
    prompt = Column(Text, nullable=False)
    description = Column(Text, nullable=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    organization_agent_id = Column(
        Integer,
        ForeignKey("organization_agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    agent_type = Column(String(50), nullable=True, index=True)
    model = Column(String(80), nullable=True)
    context_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    organization = relationship("Organization")
    organization_agent = relationship("OrganizationAgents")


