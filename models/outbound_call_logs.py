from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from core.database import Base


class OutboundCallLog(Base):
    __tablename__ = "outbound_call_logs"

    id = Column(Integer, primary_key=True, index=True)
    agent_id = Column(String(255), nullable=False)
    phone_number = Column(String(20), nullable=True)
    params = Column(JSON, nullable=True)
    response = Column(JSON, nullable=True)
    success = Column(Boolean, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<OutboundCallLog(id={self.id}, agent_id='{self.agent_id}', success={self.success})>"
