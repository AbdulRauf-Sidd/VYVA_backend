from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.sql import func

from core.database import Base


class ManualCall(Base):
    """An outbound call to a user triggered from the admin panel (immediately or scheduled)."""

    __tablename__ = "manual_calls"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(36), index=True, nullable=False)  # groups calls created in one submit
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    agent_id = Column(String(255), nullable=True)
    phone_number = Column(String(30), nullable=True)
    override_first_message = Column(Text, nullable=True)
    override_prompt = Column(Text, nullable=True)
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)  # UTC
    # scheduled -> queued -> placed | failed ; cancelled
    status = Column(String(20), nullable=False, default="scheduled", index=True)
    conversation_id = Column(String(100), nullable=True, index=True)  # ElevenLabs id, joins eleven_labs_sessions.call_sid
    error = Column(Text, nullable=True)
    placed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
