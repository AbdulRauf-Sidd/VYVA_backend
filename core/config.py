"""
Configuration settings for Vyva Backend.

Uses Pydantic Settings for environment variable management.
"""

import os
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""
    
    # Environment
    ENV: str = Field(default="development", env="ENV")
    DEBUG: bool = Field(default=False, env="DEBUG")
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Logging Control
    ENABLE_FILE_LOGGING: bool = Field(default=True, env="ENABLE_FILE_LOGGING")
    ENABLE_REQUEST_LOGGING: bool = Field(default=True, env="ENABLE_REQUEST_LOGGING")
    
    # Application
    APP_NAME: str = Field(default="Vyva Backend", env="APP_NAME")
    VERSION: str = Field(default="1.0.0", env="VERSION")
    
    # Server
    HOST: str = Field(default="0.0.0.0", env="HOST")
    PORT: int = Field(default=8000, env="PORT")

    REDIS_URL: str = Field(default="redis://localhost:6379/0", env="REDIS_URL")
    CELERY_BROKER_URL: str = REDIS_URL
    CELERY_RESULT_BACKEND: str = REDIS_URL

    origins: List[str] = [
        "http://localhost:8080",  # frontend URL
        "http://localhost:5173",
        "https://vyva.io", # production frontend
        "https://4f214c49a3b2.ngrok-free.app"
    ]
    
    # CORS
    # ALLOWED_HOSTS: List[str] = Field(
    #     default=["*"],
    #     env="ALLOWED_HOSTS"
    # )

    DATABASE_URL: Optional[str] = Field(default=None, env="DATABASE_URL")
    PRODUCTION_DATABASE_URL: Optional[str] = Field(default=None, env="PRODUCTION_DATABASE_URL")

    OTP_TTL_MINUTES: int = 10
    MAX_ATTEMPTS: int = 5

    SESSION_DURATION: int = 60 * 24 * 90  # 90 days

    FRONTEND_URL: str = Field(default="vyva.io", env="FRONTEND_URL")


    @property
    def database_url(self) -> str:
        if self.ENV == "development":
            return self.DATABASE_URL or ""
        return self.PRODUCTION_DATABASE_URL or ""    
    
        
    DATABASE_POOL_SIZE: int = Field(default=10, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    
    # Security
    SECRET_KEY: str = Field(
        default="secret-key",
        env="SECRET_KEY"
    )
    ALGORITHM: str = Field(default="HS256", env="ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(
        default=15,
        env="ACCESS_TOKEN_EXPIRE_MINUTES"
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(
        default=180,
        env="REFRESH_TOKEN_EXPIRE_DAYS"
    )
    
    # Email Configuration
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USER: Optional[str] = Field(default=None, env="SMTP_USER")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    SMTP_TLS: bool = Field(default=True, env="SMTP_TLS")
    SMTP_SSL: bool = Field(default=False, env="SMTP_SSL")

    MAILGUN_API_URL: Optional[str] = Field(default=None, env="MAILGUN_API_URL")

    MAILGUN_API_KEY: Optional[str] = Field(default=None, env="MAILGUN_API_KEY")
    
    # SMS Configuration (Twilio)
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, env="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, env="TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None, env="TWILIO_PHONE_NUMBER")
    
    # WhatsApp Configuration (Twilio)
    TWILIO_WHATSAPP_FROM_NUMBER: Optional[str] = Field(default=None, env="TWILIO_WHATSAPP_FROM_NUMBER")
    TWILIO_WHATSAPP_TEMPLATE_SID: Optional[str] = Field(default=None, env="TWILIO_WHATSAPP_TEMPLATE_SID")
    TWILIO_WHATSAPP_REMINDER_TEMPLATE_SID: Optional[str] = Field(default=None, env="TWILIO_WHATSAPP_REMINDER_TEMPLATE_SID")
    TWILIO_WHATSAPP_BRAIN_COACH_TEMPLATE_SID: Optional[str] = Field(default=None, env="TWILIO_WHATSAPP_BRAIN_COACH_TEMPLATE_SID")

    
    # ElevenLabs TTS
    ELEVENLABS_API_KEY: Optional[str] = Field(default=None, env="ELEVENLABS_API_KEY")
    ELEVENLABS_BASE_URL: str = Field(
        default="https://api.elevenlabs.io",
        env="ELEVENLABS_BASE_URL"
    )
    ELEVENLABS_HEADER_KEY: Optional[str] = Field(
        default="xi-api-key",
        env="ELEVENLABS_HEADER_KEY"
    )
    ELEVENLABS_MEDICATION_AGENT_ID: Optional[str] = Field(
        default=None,
        env="ELEVENLABS_MEDICATION_AGENT_ID"
    )
    ELEVENLABS_AGENT_PHONE_NUMBER_ID: Optional[str] = Field(
        default=None,
        env="ELEVENLABS_AGENT_PHONE_NUMBER"
    )
    ELEVENLABS_FALL_DETECTION_AGENT_ID: Optional[str] = Field(
        default=None,
        env="ELEVENLABS_FALL_DETECTION_AGENT_ID"
    )

    ELEVENLABS_EMERGENCY_AGENT_ID: Optional[str] = Field(
        default=None,
        env="ELEVENLABS_EMERGENCY_AGENT_ID"
    )

    OPENAI_MODEL: Optional[str] = Field(
        default=None,
        env="OPENAI_MODEL"
    )

    OPENAI_MAX_TOKENS: Optional[int] = Field(
        default=None,
        env="OPENAI_MAX_TOKENS"
    )

    OPENAI_TEMPERATURE: Optional[float] = Field(
        default=None,
        env="OPENAI_TEMPERATURE"
    )

    OPENAI_API_KEY: Optional[str] = Field(
        default=None,
        env="OPENAI_API_KEY"
    )

    OPENAI_WORKFLOW_ID: Optional[str] = Field(
        default=None,
        env="OPENAI_WORKFLOW_ID"
    )

    SERP_API_KEY: Optional[str] = Field(
        default=None,
        env="SERP_API_KEY"
    )
    
    SERP_BASE_URL: Optional[str] = Field(default=None, env='SERP_BASE_URL')
    
    # Sentry (Optional)
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    SENTRY_ENVIRONMENT: str = Field(default="development", env="SENTRY_ENVIRONMENT")
    
    # Redis (Optional, for caching)
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")

    # Google Places (v1)
    GOOGLE_PLACES_API_KEY: Optional[str] = Field(default=None, env="GOOGLE_PLACES_API_KEY")
    GOOGLE_PLACES_BASE_URL: str = Field(default="https://places.googleapis.com/v1", env="GOOGLE_PLACES_BASE_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


# Create settings instance
settings = Settings()


def get_env_file() -> str:
    """Get the appropriate environment file based on ENV setting."""
    env_file = f".env.{settings.ENV}"
    if os.path.exists(env_file):
        return env_file
    return ".env"


# Update settings with environment-specific file
settings = Settings(_env_file=get_env_file()) 