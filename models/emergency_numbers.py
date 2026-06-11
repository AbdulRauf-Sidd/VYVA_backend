from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum as SQLEnum
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum

from core.database import Base


class EmergencyNumberTypeEnum(str, PyEnum):
    check_in_misses = "check_in_misses"
    emergency_call = "emergency_call"


class EmergencyNumber(Base):
    __tablename__ = "emergency_numbers"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), nullable=False)
    type = Column(String(30), nullable=False)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    organization = relationship("Organization", back_populates="emergency_numbers")

    def __repr__(self):
        return f"<EmergencyNumber(id={self.id}, type='{self.type}', org={self.organization_id})>"
