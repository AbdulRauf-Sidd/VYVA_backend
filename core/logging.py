"""
Logging configuration for Vyva Backend.

Uses structlog for structured logging with JSON output and file-based logging.
"""

import logging
import sys
import os
from datetime import datetime
from typing import Any, Dict
import structlog
from structlog.stdlib import LoggerFactory

from core.config import settings


def setup_logging() -> structlog.stdlib.BoundLogger:
    """Setup structured logging configuration with file-based logging."""
    
    # Create logs directory if it doesn't exist
    logs_dir = "logs"
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer() if not settings.DEBUG else structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Create formatters
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.LOG_LEVEL.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handlers (only if enabled in settings)
    if getattr(settings, 'ENABLE_FILE_LOGGING', True):
        # General application log
        app_log_file = os.path.join(logs_dir, f"app_{datetime.now().strftime('%Y%m%d')}.log")
        app_file_handler = logging.FileHandler(app_log_file, encoding='utf-8')
        app_file_handler.setFormatter(file_formatter)
        app_file_handler.setLevel(logging.INFO)
        root_logger.addHandler(app_file_handler)
        
        # Error log
        error_log_file = os.path.join(logs_dir, f"error_{datetime.now().strftime('%Y%m%d')}.log")
        error_file_handler = logging.FileHandler(error_log_file, encoding='utf-8')
        error_file_handler.setFormatter(file_formatter)
        error_file_handler.setLevel(logging.ERROR)
        root_logger.addHandler(error_file_handler)
    
    # Request/Response logging (only if enabled in settings)
    if getattr(settings, 'ENABLE_REQUEST_LOGGING', True):
        request_log_file = os.path.join(logs_dir, f"requests_{datetime.now().strftime('%Y%m%d')}.log")
        request_logger = logging.getLogger("requests")
        request_logger.setLevel(logging.INFO)
        
        # Prevent propagation to root logger to avoid duplicate logs
        request_logger.propagate = False
        
        request_file_handler = logging.FileHandler(request_log_file, encoding='utf-8')
        request_file_handler.setFormatter(file_formatter)
        request_logger.addHandler(request_file_handler)
    
    # Create logger
    logger = structlog.get_logger()
    
    # Add Sentry integration if configured
    if (settings.SENTRY_DSN and 
        settings.SENTRY_DSN.strip() and 
        not settings.SENTRY_DSN.startswith('your-sentry')):
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            integrations=[
                FastApiIntegration(),
                SqlalchemyIntegration(),
            ],
            traces_sample_rate=0.1 if settings.ENV == "production" else 1.0,
        )
        
        logger.info("Sentry integration enabled", environment=settings.SENTRY_ENVIRONMENT)
    
    return logger


def get_logger(name: str = None) -> structlog.stdlib.BoundLogger:
    """Get a logger instance."""
    return structlog.get_logger(name)


# Request logging middleware
async def log_request_middleware(request, call_next):
    """Log incoming requests."""
    logger = get_logger("request")
    
    # Log request
    logger.info(
        "Request started",
        method=request.method,
        url=str(request.url),
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    
    # Process request
    response = await call_next(request)
    
    # Log response
    logger.info(
        "Request completed",
        method=request.method,
        url=str(request.url),
        status_code=response.status_code,
    )
    
    return response 

