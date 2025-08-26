"""
Profile model for user profile information.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


# class Profile(Base):
#     """Profile model for user profile information."""
    
#     __tablename__ = "profiles"
    
#     id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # # Personal Information
    # avatar_url = Column(String(500), nullable=True)
    # bio = Column(Text, nullable=True)
    # address = Column(Text, nullable=True)
    # city = Column(String(100), nullable=True)
    # state = Column(String(100), nullable=True)
    # zip_code = Column(String(20), nullable=True)
    # country = Column(String(100), nullable=True)
    
    # # Health Information
    # height_cm = Column(Integer, nullable=True)
    # weight_kg = Column(Integer, nullable=True)
    # blood_type = Column(String(10), nullable=True)
    # allergies = Column(Text, nullable=True)
    # medical_conditions = Column(Text, nullable=True)
    
    # # Preferences
    # language = Column(String(10), default="en")
    # timezone = Column(String(50), default="UTC")
    # notification_preferences = Column(Text, nullable=True)  # JSON string
    
    # # Emergency Settings
    # emergency_contact_enabled = Column(Boolean, default=True)
    # fall_detection_enabled = Column(Boolean, default=True)
    # medication_reminders_enabled = Column(Boolean, default=True)
    
    # # Timestamps
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # # Relationships
    # user = relationship("User", back_populates="profile")
    
    # def __repr__(self):
    #     return f"<Profile(id={self.id}, user_id={self.user_id})>" 