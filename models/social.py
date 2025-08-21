"""
Social model for social features and connections.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class Social(Base):
    """Social model for social features and connections."""
    
    __tablename__ = "social"
    
    id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # # Social Connection
    # connection_name = Column(String(255), nullable=False)
    # connection_type = Column(String(50), nullable=False)  # family, friend, caregiver, doctor
    # phone_number = Column(String(20), nullable=True)
    # email = Column(String(255), nullable=True)
    # relationship = Column(String(100), nullable=True)  # spouse, child, friend, etc.
    
    # # Communication Preferences
    # preferred_contact_method = Column(String(50), nullable=True)  # phone, email, text, app
    # notification_frequency = Column(String(50), nullable=True)  # daily, weekly, monthly
    
    # # Status
    # is_active = Column(Boolean, default=True)
    # is_emergency_contact = Column(Boolean, default=False)
    
    # # Timestamps
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # # Relationships
    # user = relationship("User", back_populates="social_connections")
    
    # def __repr__(self):
    #     return f"<Social(id={self.id}, connection_name='{self.connection_name}', user_id={self.user_id})>" 