"""
Vyva Backend - FastAPI Application Entry Point

A production-ready FastAPI backend for senior care applications.
"""

import os
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import settings
from core.logging import setup_logging
from core.database import engine, Base
from api.v1 import auth, users, profiles, health_care, social, brain_coach, medications, fall_detection, emergency, tts, symptom_checker


# Setup logging
logger = setup_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Vyva Backend application...")
    
    # Create database tables (for development)
    if settings.ENV == "development":
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created (development mode)")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Vyva Backend application...")


# Create FastAPI application
app = FastAPI(
    title="Vyva Backend API",
    description="A production-ready FastAPI backend for senior care applications",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_HOSTS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation exceptions."""
    logger.error(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": exc.errors()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions."""
    logger.error(f"Unhandled Exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"}
    )


# # Health check endpoints
# @app.get("/health")
# async def health_check() -> Dict[str, Any]:
#     """Basic health check endpoint."""
#     return {
#         "status": "healthy",
#         "service": "vyva-backend",
#         "version": "1.0.0"
#     }


# @app.get("/health/db")
# async def database_health_check() -> Dict[str, Any]:
#     """Database health check endpoint."""
#     try:
#         # Test database connection
#         async with engine.begin() as conn:
#             await conn.execute("SELECT 1")
#         return {
#             "status": "healthy",
#             "database": "connected"
#         }
#     except Exception as e:
#         logger.error(f"Database health check failed: {str(e)}")
#         return {
#             "status": "unhealthy",
#             "database": "disconnected",
#             "error": str(e)
#         }


# @app.get("/health/services")
# async def services_health_check() -> Dict[str, Any]:
#     """External services health check endpoint."""
#     services_status = {
#         "email_service": "unknown",
#         "sms_service": "unknown",
#         "tts_service": "unknown"
#     }
    
#     # Add service health checks here
#     # This is a placeholder for actual service health checks
    
#     return {
#         "status": "healthy",
#         "services": services_status
#     }


# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["Profiles"])
app.include_router(health_care.router, prefix="/api/v1/health-care", tags=["Health & Care"])
app.include_router(social.router, prefix="/api/v1/social", tags=["Social"])
app.include_router(brain_coach.router, prefix="/api/v1/brain-coach", tags=["Brain Coach"])
app.include_router(medications.router, prefix="/api/v1/medications", tags=["Medications"])
app.include_router(fall_detection.router, prefix="/api/v1/fall-detection", tags=["Fall Detection"])
app.include_router(emergency.router, prefix="/api/v1/emergency", tags=["Emergency Contacts"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["Text-to-Speech"])
app.include_router(symptom_checker.router, prefix="/api/v1/symptoms", tags=["Symptoms Checker"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 