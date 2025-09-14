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
    DEBUG: bool = Field(default=True, env="DEBUG")
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
    
    # CORS
    ALLOWED_HOSTS: List[str] = Field(
        default=["*"],
        env="ALLOWED_HOSTS"
    )

    DATABASE_URL: Optional[str] = Field(default=None, env="DATABASE_URL")
    PRODUCTION_DATABASE_URL: Optional[str] = Field(default=None, env="PRODUCTION_DATABASE_URL")


    @property
    def database_url(self) -> str:
        print('hi')
        if self.ENV == "development":
            return self.DATABASE_URL or ""
        return self.PRODUCTION_DATABASE_URL or ""    
    
    # # Database
    # if ENV == 'development':
    #     DATABASE_URL: str = Field(
    #         env="DATABASE_URL"
    #     )
    # else:
    #     DATABASE_URL: str = Field(
    #         env="PRODUCTION_DATABASE_URL"
    #     )
        
    DATABASE_POOL_SIZE: int = Field(default=10, env="DATABASE_POOL_SIZE")
    DATABASE_MAX_OVERFLOW: int = Field(default=20, env="DATABASE_MAX_OVERFLOW")
    
    # Security
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
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
    
    # Sentry (Optional)
    SENTRY_DSN: Optional[str] = Field(default=None, env="SENTRY_DSN")
    SENTRY_ENVIRONMENT: str = Field(default="development", env="SENTRY_ENVIRONMENT")
    
    # Redis (Optional, for caching)
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


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