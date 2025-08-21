"""
FallDetection model for fall detection and safety monitoring.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Boolean, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from core.database import Base


class FallDetection(Base):
    """FallDetection model for fall detection and safety monitoring."""
    
    __tablename__ = "fall_detection"
    
    id = Column(Integer, primary_key=True, index=True)
    # user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # # Fall Event Details
    # event_type = Column(String(50), nullable=False)  # fall_detected, false_alarm, test
    # confidence_score = Column(Float, nullable=True)  # 0.0 to 1.0
    # severity_level = Column(String(50), nullable=True)  # low, medium, high, critical
    
    # # Location and Context
    # location = Column(String(255), nullable=True)  # room, outdoor, bathroom, etc.
    # gps_coordinates = Column(String(100), nullable=True)  # latitude,longitude
    # device_id = Column(String(100), nullable=True)
    
    # # Sensor Data
    # accelerometer_data = Column(Text, nullable=True)  # JSON array of sensor readings
    # gyroscope_data = Column(Text, nullable=True)  # JSON array of sensor readings
    # impact_force = Column(Float, nullable=True)
    
    # # Response and Actions
    # response_time_seconds = Column(Float, nullable=True)
    # emergency_services_called = Column(Boolean, default=False)
    # family_notified = Column(Boolean, default=False)
    # caregiver_notified = Column(Boolean, default=False)
    
    # # User Response
    # user_responded = Column(Boolean, default=False)
    # user_response_time_seconds = Column(Float, nullable=True)
    # user_ok = Column(Boolean, nullable=True)  # True if user confirmed they're okay
    
    # # Notes and Follow-up
    # notes = Column(Text, nullable=True)
    # follow_up_required = Column(Boolean, default=False)
    # follow_up_completed = Column(Boolean, default=False)
    
    # # Timestamps
    # detected_at = Column(DateTime(timezone=True), server_default=func.now())
    # responded_at = Column(DateTime, nullable=True)
    # resolved_at = Column(DateTime, nullable=True)
    # created_at = Column(DateTime(timezone=True), server_default=func.now())
    # updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # # Relationships
    # user = relationship("User", back_populates="fall_detections")
    
    # def __repr__(self):
    #     return f"<FallDetection(id={self.id}, event_type='{self.event_type}', user_id={self.user_id})>" 