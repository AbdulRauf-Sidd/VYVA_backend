from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.sql import func
from core.database import Base


class ElevenLabsSessions(Base):
    __tablename__ = "eleven_labs_sessions"

    id = Column(Integer, primary_key=True, index=True)
    call_successful = Column(String(20), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    agent_id = Column(String(80), nullable=True)
    duration = Column(Integer, nullable=True)
    status = Column(String(20), nullable=True)
    call_sid = Column(String(100), nullable=True)
    termination_reason = Column(String(40), nullable=True)
    summary = Column(Text, nullable=True)
    transcription = Column(JSON, nullable=True)
    created = Column(DateTime(timezone=True), server_default=func.now())
