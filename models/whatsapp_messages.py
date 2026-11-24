from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from core.database import Base


class WhatsappMessage(Base):
    """Every WhatsApp message sent to or received from a user via Meta."""

    __tablename__ = "whatsapp_messages"

    id = Column(Integer, primary_key=True, index=True)
    direction = Column(String(3), nullable=False)  # 'out' | 'in'
    phone_number = Column(String(30), nullable=False, index=True)  # the user's number, digits only
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    wa_message_id = Column(String(255), nullable=True, unique=True, index=True)  # Meta's wamid
    message_type = Column(String(30), nullable=True)  # template | text | button | interactive | image ...
    template_name = Column(String(255), nullable=True)
    body = Column(Text, nullable=True)  # text, or button text for replies
    payload = Column(JSON, nullable=True)  # template params / button payload / raw incoming message
    status = Column(String(20), nullable=True)  # out: sent|delivered|read|failed; in: received
    error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
