"""
User model for authentication and user management.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from enum import Enum as PyEnum
from models.organization import Organization
from models.elevenlabs_agents import ElevenLabsAgents
from core.database import Base


class PreferredConsultationLanguageEnum(str, PyEnum):
    ENGLISH = "English"
    SPANISH = "Spanish"
    GERMAN = "German"
    FRENCH = "French"

class PreferredReportsChannelEnum(str, PyEnum):
    WHATSAPP = "whatsapp"
    EMAIL = "email"
    

class BrainCoachComplexityEnum(str, PyEnum):
    EASY = "Easy"
    MEDIUM = "Medium"
    ADVANCED = "Advanced"
    PROGRESSIVE = "Progressive"

#-------------------------------------------------------

class User(Base):
    """User model for authentication and user management."""
    
    __tablename__ = "users"
    
    #Main
    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    email = Column(String(255), index=True, nullable=True, unique=True) #TODO make unique true
    phone_number = Column(String(20), nullable=False, unique=True)
    # land_line = Column(String(20), nullable=True)
    is_primary_landline = Column(Boolean, nullable=True, default=False)
    age = Column(Integer, nullable=True)
    # living_situation = Column(SQLEnum(LivingSituation), nullable=True)
    admin_profile = relationship("AdminUser", back_populates="user", uselist=False)
    timezone=Column(String(30), nullable=True)
    date_of_birth = Column(DateTime, nullable=True)
    organization = relationship("Organization", back_populates="users")
    organization_id = Column(Integer, ForeignKey("organizations.id"), nullable=True)
    preferred_consultation_language = Column(SQLEnum(PreferredConsultationLanguageEnum), nullable=True)
    preferred_communication_channel = Column(String(50), nullable=True)
    onboarding_user_id = Column(Integer, ForeignKey("onboarding_users.id"), nullable=True, unique=True)
    onboarding_user = relationship("OnboardingUser", backref="user", uselist=False)
    secondary_phone = Column(String(20), nullable=True, unique=True)

    #Health and Care
    health_conditions = Column(Text, nullable=True)
    mobility = Column(String(255), nullable=True)


    #Social Companion
    password_hash = Column(String(255), nullable=True)
    local_event_recommendations = Column(Boolean, nullable=True)

    #sessions
    # scheduled_sessions = relationship("ScheduledSession", back_populates="user", cascade="all, delete-orphan")
    user_checkins = relationship("UserCheckin", back_populates="user", cascade="all, delete-orphan")


    #Medications
    medications = relationship("Medication", back_populates="user", cascade="all, delete-orphan")
    wants_caretaker_alerts = Column(Boolean, nullable=True, default = True)
    wants_reminders = Column(Boolean, nullable=True)
    takes_medication = Column(Boolean, nullable=True)
    missed_dose_alerts = Column(Boolean, nullable=True)
    preferred_reminder_channel = Column(String(50), nullable=True)
    medication_logs = relationship(
        "MedicationLog",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    # escalate_to_emergency_contact = Column(Boolean, nullable=True)
    symptom_checker_responses = relationship("SymptomCheckerResponse", back_populates="user", cascade="all, delete-orphan")

    #Reminders
    # preferred_channel = Column(String(50), nullable=True)
    whatsapp_reports = Column(Boolean, nullable=True, default=False)
    email_reports = Column(Boolean, nullable=True, default=False)
    preferred_reports_channel = Column(String(20), default='whatsapp', nullable=True)

    
    #Care taker
    caretaker_id = Column(Integer, ForeignKey("caretakers.id"), nullable=True, index=True) 
    caretaker = relationship("Caretaker", back_populates="assigned_users")
    caretaker_consent = Column(Boolean, nullable=True)
    
    emergency_contact_name = Column(String(80), nullable=True)
    emergency_contact_email = Column(String(255), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    emergency_line_phone = Column(String(20), nullable=True)
    
    
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
    address = Column(Text, nullable=True)

    #Brain Coach
    brain_coach_complexity = Column(SQLEnum(BrainCoachComplexityEnum), nullable=True)  
    
    #Nutrition Services
    nutrition_services_activation = Column(Boolean, nullable=True)

    #Concierge Services
    concierge_services_activation = Column(Boolean, nullable=True)

    #Scam Protection
    scam_protection_activation = Column(Boolean, nullable=True)


    #Fall Detection
    fall_detection_activation = Column(Boolean, nullable=True, default=True)
    fall_auto_alert_to_caregiver = Column(Boolean, nullable=True, default=True) 
    

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
    
    @property
    def full_address(self) -> str:
        """Return the user's full address as a readable string."""
        parts = [
            self.street,
            self.city,
            self.postal_code,
            self.country,
            self.address
        ]
    
        # Filter out None / empty / whitespace-only values
        parts = [p.strip() for p in parts if p and p.strip()]
    
        return ", ".join(parts) if parts else "No address provided"

    

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
    


class Caretaker(Base):
    __tablename__ = "caretakers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=True)
    phone_number = Column(String(20), nullable=True, unique=True)
    is_active = Column(Boolean, default=True)
    # username = Column(String(100), unique=True, nullable=False)
    # password_hash = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    assigned_users = relationship("User", back_populates="caretaker")

    @property
    def full_name(self) -> str:
        """Get user's full name."""
        return self.name 
    

    def __repr__(self):
        return f"<Caretaker(id={self.id}, name='{self.name}')>"