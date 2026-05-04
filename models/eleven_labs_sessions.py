from sqlalchemy import Column, Float, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from core.database import Base


class ElevenLabsSessions(Base):
    __tablename__ = "eleven_labs_sessions"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String(255), unique=True, index=True, nullable=True)
    call_successful = Column(String(20), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    agent_id = Column(String(255), nullable=True)
    agent_type = Column(String(50), nullable=True)
    event_type = Column(String(80), nullable=True)
    event_timestamp = Column(DateTime(timezone=True), nullable=True)
    payload = Column(JSON, nullable=True)
    call_metadata = Column("metadata", JSON, nullable=True)
    analysis = Column(JSON, nullable=True)
    dynamic_variables = Column(JSON, nullable=True)
    duration = Column(Integer, nullable=True)
    cost = Column(Float, nullable=True)
    status = Column(String(20), nullable=True)
    call_sid = Column(String(100), nullable=True)
    phone_number = Column(String(30), nullable=True)
    termination_reason = Column(String(100), nullable=True)
    summary = Column(Text, nullable=True)
    transcription = Column(JSON, nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
