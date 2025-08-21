"""
User model for authentication and user management.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class User(Base):
    """User model for authentication and user management."""
    
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    # email = Column(String(255), unique=True, index=True, nullable=False)
    # hashed_password = Column(String(255), nullable=False)
    # first_name = Column(String(100), nullable=True)
    # last_name = Column(String(100), nullable=True)
    # phone_number = Column(String(20), nullable=True)
    # date_of_birth = Column(DateTime, nullable=True)
    # is_active = Column(Boolean, default=True)
    # is_verified = Column(Boolean, default=False)
    # is_superuser = Column(Boolean, default=False)
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    # last_login = Column(DateTime(timezone=True), nullable=True)
    
    # # Relationships
    # profile = relationship("Profile", back_populates="user", uselist=False)
    # health_care_records = relationship("HealthCare", back_populates="user")
    # social_connections = relationship("Social", back_populates="user")
    # brain_coach_sessions = relationship("BrainCoach", back_populates="user")
    # medications = relationship("Medication", back_populates="user")
    # fall_detections = relationship("FallDetection", back_populates="user")
    # emergency_contacts = relationship("EmergencyContact", back_populates="user")
    
    # def __repr__(self):
    #     return f"<User(id={self.id}, email='{self.email}')>"
    
    # @property
    # def full_name(self) -> str:
    #     """Get user's full name."""
    #     if self.first_name and self.last_name:
    #         return f"{self.first_name} {self.last_name}"
    #     elif self.first_name:
    #         return self.first_name
    #     elif self.last_name:
    #         return self.last_name
    #     return self.email 