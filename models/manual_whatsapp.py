from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from core.database import Base


class ManualWhatsapp(Base):
    """A template WhatsApp to a user triggered from the admin panel (immediately or scheduled)."""

    __tablename__ = "manual_whatsapp"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(36), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    template_name = Column(String(255), nullable=False)  # Meta template name
    language = Column(String(30), nullable=True)  # repo language name
    variables = Column(JSON, nullable=True)  # {"1": "text with {first_name}"}
    scheduled_at = Column(DateTime(timezone=True), nullable=False, index=True)  # UTC
    status = Column(String(20), nullable=False, default="scheduled", index=True)  # scheduled|queued|sent|failed|cancelled
    wa_message_id = Column(String(255), nullable=True, index=True)  # joins whatsapp_messages.wa_message_id
    error = Column(Text, nullable=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
