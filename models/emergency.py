"""
EmergencyContact model for emergency contact management.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class EmergencyContact(Base):
    """EmergencyContact model for emergency contact management."""
    
    __tablename__ = "emergency_contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # # Contact Information
    # name = Column(String(255), nullable=False)
    # relationship = Column(String(100), nullable=False)  # spouse, child, friend, doctor, etc.
    # phone_number = Column(String(20), nullable=False)
    # email = Column(String(255), nullable=True)
    # address = Column(Text, nullable=True)
    
    # # Contact Preferences
    # contact_order = Column(Integer, default=1)  # 1 = primary, 2 = secondary, etc.
    # notification_method = Column(String(50), default="phone")  # phone, email, text, all
    # can_make_medical_decisions = Column(Boolean, default=False)
    
    # # Medical Information
    # is_healthcare_provider = Column(Boolean, default=False)
    # provider_type = Column(String(100), nullable=True)  # doctor, nurse, specialist, etc.
    # medical_notes = Column(Text, nullable=True)
    
    # # Status
    # is_active = Column(Boolean, default=True)
    # is_verified = Column(Boolean, default=False)
    
    # # Timestamps
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # # Relationships
    # user = relationship("User", back_populates="emergency_contacts")
    
    # def __repr__(self):
    #     return f"<EmergencyContact(id={self.id}, name='{self.name}', user_id={self.user_id})>" 