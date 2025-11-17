"""
User model for authentication and user management.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from models.organization import Organization

from core.database import Base

#ENUM VALUES
class LivingSituation(str, PyEnum):
    """Enum for living situation options."""
    ALONE = "Alone"
    WITH_PARTNER = "With Partner"
    WITH_FAMILY = "With Family"


class MobilityEnum(str, PyEnum):
    INDEPENDENT = "Independent"
    WALK_WITH_ASSISTANCE = "Walk with assistance"
    WHEELCHAIR = "Wheelchair"
    BED_BOUND = "Bed-bound"

class PreferredDoctorTypeEnum(str, PyEnum):
    MY_OWN = "My own"
    ANY_AVAILABLE = "Any available"
    SPECIALIST = "Specialist"  

class PreferredConsultationTypeEnum(str, PyEnum):
    PHONE = "Phone"
    VIDEO = "Video"

class PreferredConsultationLanguageEnum(str, PyEnum):
    ENGLISH = "English"
    SPANISH = "Spanish"
    GERMAN = "German"
    FRENCH = "French"

class BrainCoachTimeEnum(str, PyEnum):
    MORNING = "Morning"
    AFTERNOON = "Afternoon"
    EVENING = "Evening"

class BrainCoachComplexityEnum(str, PyEnum):
    EASY = "Easy"
    MEDIUM = "Medium"
    ADVANCED = "Advanced"
    PROGRESSIVE = "Progressive"

class RegularSafetyCheckInsEnum(str, PyEnum):
    DAILY = "Daily"
    TWICE_DAILY = "Twice Daily"
    # CUSTOM = "Custom" // Ask


class PreferredCheckInTimeEnum(str, PyEnum):
    EARLY_MORNING = "Early Morning (6–9 AM)"
    LATE_MORNING = "Late Morning"
    EARLY_AFTERNOON = "Early Afternoon"
    LATE_AFTERNOON = "Late Afternoon"
    EVENING = "Evening"
    NIGHT = "Night"

class CheckInFrequencyEnum(str, PyEnum):
    MULTIPLE_PER_DAY = "Multiple per day"
    DAILY = "Daily"
    SEVERAL_PER_WEEK = "Several per week"
    WEEKLY = "Weekly"
    EMERGENCIES_ONLY = "Emergencies only"
    WEEKENDS_ONLY = "Weekends only"
    HOLIDAYS = "Holidays/special occasions"

#-------------------------------------------------------

class User(Base):
    """User model for authentication and user management."""
    
    __tablename__ = "users"
    
    #Main
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), index=True, nullable=True) #TODO make unique true
    phone_number = Column(String(20), nullable=True)
    land_line = Column(String(20), nullable=True)
    age = Column(Integer, nullable=True)
    living_situation = Column(SQLEnum(LivingSituation), nullable=True)
    admin_profile = relationship("AdminUser", back_populates="user", uselist=False)
    date_of_birth = Column(DateTime, nullable=True)
    organization = relationship("Organization", back_populates="users")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    preferred_consultation_language = Column(SQLEnum(PreferredConsultationLanguageEnum), nullable=True)
    preferred_communication_channel = Column(String(50), nullable=True)

    # Agents
    eleven_labs_agents = relationship("ElevenLabsUserAgents", back_populates="user")

    #Health and Care
    health_conditions = Column(Text, nullable=True)
    mobility = Column(String(255), nullable=True)


    #Social Companion
    password_hash = Column(String(255), nullable=True)
    social_check_ins = Column(Boolean, nullable=True)
    faith = Column(String(20), nullable=True)
    local_event_recommendations = Column(Boolean, nullable=True)
    preferred_check_in_time = Column(SQLEnum(PreferredCheckInTimeEnum), nullable=True)
    check_in_frequency = Column(SQLEnum(CheckInFrequencyEnum), nullable=True)
    topics_of_interest = Column(String(500), nullable=True)
    preferred_activities = Column(String(500), nullable=True)


    #Medications
    medications = relationship("Medication", back_populates="user", cascade="all, delete-orphan")
    wants_caretaker_alerts = Column(Boolean, nullable=True, default = True)
    wants_reminders = Column(Boolean, nullable=True)
    takes_medication = Column(Boolean, nullable=True)
    missed_dose_alerts = Column(Boolean, nullable=True)
    escalate_to_emergency_contact = Column(Boolean, nullable=True)
    preferred_doctor_type = Column(SQLEnum(PreferredDoctorTypeEnum), nullable=True)

    #Reminders
    preferred_channel = Column(String(50), nullable=True)
    whatsapp_reports = Column(Boolean, nullable=False, default=False)
    email_reports = Column(Boolean, nullable=False, default=False)
    preferred_communication_channel = Column(String(50), nullable=True)


    #Caretaker Information
    caretaker_id = Column(Integer, ForeignKey("caretakers.id"), nullable=True, index=True) 
    caretaker = relationship("CareTaker", back_populates="assigned_users")
    
    emergency_contact_name = Column(String(80), nullable=True)
    emergency_contact_email = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)
    
    
    #Auth
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    # hashed_password = Column(String(255), nullable=False)

    # Address fields
    street = Column(String(255), nullable=True)
    city = Column(String(100), nullable=True)  
    postal_code = Column(String(20), nullable=True)  
    country = Column(String(100), nullable=True)

    #Brain Coach
    brain_coach_activation = Column(Boolean, nullable=True)
    brain_coach_time = Column(SQLEnum(BrainCoachTimeEnum), nullable=True) 
    brain_coach_complexity = Column(SQLEnum(BrainCoachComplexityEnum), nullable=True)  
    performance_reports = Column(Boolean, nullable=True, default=True)  

    #Nutrition Services
    nutrition_services_activation = Column(Boolean, nullable=True)

    #Concierge Services
    concierge_services_activation = Column(Boolean, nullable=True)

    #Scam Protection
    scam_protection_activation = Column(Boolean, nullable=True)


    #Fall Detection
    fall_detection_activation = Column(Boolean, nullable=True, default=True)
    fall_auto_alert_to_caregiver = Column(Boolean, nullable=True, default=True) 
    
    # regular_safety_check_ins = Column(SQLEnum(RegularSafetyCheckInsEnum), nullable=True)  # Single select enum

    
    #Doctor and Pharmacy
    # primary_doctor_name = Column(String(255), nullable=True)
    # primary_doctor_phone = Column(String(20), nullable=True)

    # preferred_pharmacy_name = Column(String(255), nullable=True)
    # preferred_pharmacy_phone = Column(String(20), nullable=True)

    # preferred_hospital_name = Column(String(255), nullable=True)
    # preferred_hospital_phone = Column(String(20), nullable=True)


    #Device Notifications
    device_token = Column(String(150), nullable=True)
    expiration = Column(String(50), nullable=True)
    p256dh = Column(String(100), nullable=True)
    auth = Column(String(100), nullable=True)


    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}')>"
    
    @property
    def full_name(self) -> str:
        """Get user's full name."""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        return self.email 
    

class AdminUser(Base):
    __tablename__ = "admin_users"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    is_superadmin = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    user = relationship("User", back_populates="admin_profile", uselist=False)
    
    def __repr__(self):
        return f"<AdminUser(id={self.id}, username='{self.username}')>"