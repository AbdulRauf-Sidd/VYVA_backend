"""
Configuration settings for the Vyva Backend application.

This module contains all configuration settings using Pydantic BaseSettings
for environment variable management and validation.
"""

from typing import Optional, List
from pydantic import BaseSettings, Field, validator
import os


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application Configuration
    APP_NAME: str = Field(default="Vyva Backend", env="APP_NAME")
    APP_VERSION: str = Field(default="1.0.0", env="APP_VERSION")
    DEBUG: bool = Field(default=False, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # Server Configuration
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")
    
    # Database Configuration
    DATABASE_URL: Optional[str] = Field(default="sqlite+aiosqlite:///./vyva.db", env="DATABASE_URL")
    
    # Security Configuration
    SECRET_KEY: str = Field(default="your-secret-key-here", env="SECRET_KEY")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    
    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = Field(default=["*"], env="ALLOWED_ORIGINS")
    ALLOWED_METHODS: List[str] = Field(default=["*"], env="ALLOWED_METHODS")
    ALLOWED_HEADERS: List[str] = Field(default=["*"], env="ALLOWED_HEADERS")
    
    # Email Configuration
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    
    # Mailgun Configuration
    MAILGUN_API_KEY: Optional[str] = Field(default=None, env="MAILGUN_API_KEY")
    MAILGUN_DOMAIN: Optional[str] = Field(default=None, env="MAILGUN_DOMAIN")
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, env="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, env="TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None, env="TWILIO_PHONE_NUMBER")
    TWILIO_WHATSAPP_FROM_NUMBER: Optional[str] = Field(default=None, env="TWILIO_WHATSAPP_FROM_NUMBER")
    TWILIO_WHATSAPP_TEMPLATE_SID: Optional[str] = Field(default=None, env="TWILIO_WHATSAPP_TEMPLATE_SID")
    
    # ElevenLabs Configuration
    ELEVENLABS_API_KEY: Optional[str] = Field(default=None, env="ELEVENLABS_API_KEY")
    ELEVENLABS_VOICE_ID: Optional[str] = Field(default=None, env="ELEVENLABS_VOICE_ID")
    ELEVENLABS_MODEL_ID: Optional[str] = Field(default=None, env="ELEVENLABS_MODEL_ID")
    ELEVENLABS_AGENT_ID: Optional[str] = Field(default=None, env="ELEVENLABS_AGENT_ID")
    ELEVENLABS_EMERGENCY_AGENT_ID: Optional[str] = Field(
        default=None,
        env="ELEVENLABS_EMERGENCY_AGENT_ID"
    )
    
    # OpenAI Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    OPENAI_MODEL: str = Field(default="gpt-4", env="OPENAI_MODEL")
    OPENAI_MAX_TOKENS: int = Field(default=2000, env="OPENAI_MAX_TOKENS")
    OPENAI_TEMPERATURE: float = Field(default=0.7, env="OPENAI_TEMPERATURE")
    
    # Note: Web search is handled by OpenAI's built-in capabilities
    
    # Sentry (Optional)
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    
    # Logging Configuration
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    LOG_FORMAT: str = Field(default="json", env="LOG_FORMAT")
    
    # MediSearch Configuration
    MEDISEARCH_API_KEY: Optional[str] = Field(default=None, env="MEDISEARCH_API_KEY")
    MEDISEARCH_API_URL: str = Field(default="https://api.medisearch.io/v1", env="MEDISEARCH_API_URL")
    
    @validator("ALLOWED_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALLOWED_METHODS", pre=True)
    def parse_cors_methods(cls, v):
        if isinstance(v, str):
            return [method.strip() for method in v.split(",")]
        return v
    
    @validator("ALLOWED_HEADERS", pre=True)
    def parse_cors_headers(cls, v):
        if isinstance(v, str):
            return [header.strip() for header in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


# Create global settings instance
settings = Settings()
