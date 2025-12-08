from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.types import JSON
from sqlalchemy.sql import func

from core.database import Base


class ElevenLabsAgents(Base):
    __tablename__ = "eleven_labs_agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    description = Column(Text, nullable=True)
    agent_id = Column(String(100), nullable=False, unique=True)
    voice_id = Column(String(100), nullable=True)
    agent_json_config = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # user_agents = relationship("ElevenLabsUserAgents", back_populates="agent")


# class ElevenLabsUserAgents(Base):
#     __tablename__ = "eleven_labs_user_agents"

#     id = Column(Integer, primary_key=True, index=True)
#     user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
#     agent_id = Column(Integer, ForeignKey("eleven_labs_agents.id"), nullable=False)
#     is_active = Column(Boolean, default=True)
#     assigned_at = Column(DateTime(timezone=True), server_default=func.now())

#     user = relationship("User", back_populates="eleven_labs_agents")
#     agent = relationship("ElevenLabsAgents")