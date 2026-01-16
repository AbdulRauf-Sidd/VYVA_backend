"""
Vyva Backend - FastAPI Application Entry Point

A production-ready FastAPI backend for senior care applications.
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Dict, Any
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
# from apscheduler.triggers.interval import IntervalTrigger
from fastapi.exceptions import RequestValidationError

from core.config import settings
from core.logging import setup_logging
from core.database import engine, Base
from api.v1 import onboarding, users, social, brain_coach, medication, fall_detection, tts, symptom_checker, post_call, ai_assistant, news, tools, organization, authentication, twilio
from api.v1.managemant import ingest_onboarding_users, call_queues
from api.v1.managemant import ingest_onboarding_users
# from apscheduler.schedulers.background import BackgroundScheduler
# from tasks import check_medication_time, run_async_job
from admin.admin import setup_admin
from core.database import AsyncSessionLocal, get_db
# from sqlalchemy.ext.asyncio import AsyncSession
# from apscheduler.schedulers.asyncio import AsyncIOScheduler
from services.elevenlabs_service import make_reminder_call_batch, check_batch_for_missed, make_caretaker_call_batch
from services.helpers import construct_whatsapp_sms_message, construct_sms_body_from_template_for_reminders
# from services.whatsapp_service import whatsapp
from services.email_service import email_service
from schemas.eleven_labs_batch_calls import ElevenLabsBatchCallCreate
from repositories.eleven_labs_batch_calls import ElevenLabsBatchCallRepository
from repositories.user import UserRepository
# from apscheduler.triggers.date import DateTrigger
from celery.app.control import Inspect
from celery_app import celery_app
from mcp_tools.mcp_instance import mcp
from mem0 import MemoryClient
from mcp_tools import user, mem0, brain_coach as brain_coach_mcp, medication as med #dont remove
import redis

# Setup logging
logger = setup_logging()

# mcp = FastMCP("Memory Tools")
mcp_app = mcp.http_app('/mcp')

# Create FastAPI application
app = FastAPI(
    title="Vyva Backend API",
    description="A production-ready FastAPI backend for senior care applications",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    openapi_url="/openapi.json" if settings.DEBUG else None,
    lifespan=mcp_app.lifespan
)



app.mount("/memory", mcp_app)

setup_admin(app) 

async def process_missed_calls(batch_id):
    logger.info(f"Proccessing missed calls for batch {batch_id}")
    phone_number_set = await check_batch_for_missed(batch_id=batch_id)
    session = AsyncSessionLocal()
    try:
        user_repo = UserRepository(session)
        users = await user_repo.get_users_by_phone_numbers(phone_number_set)
        logger.info(f"fetched {len(users)} missed medications")
        alert_by_phone = []
        for user in users:
            preferred_channel = user['caretaker_preferred_channel']
            if preferred_channel == 'phone':
                alert_by_phone.append(user)
            elif preferred_channel == 'email':
                pass
            elif preferred_channel == 'sms':
                pass
            elif preferred_channel == 'whatsapp':
                pass

        if alert_by_phone:
            logger.info(f"Making caretaker batch for missed medication for {len(alert_by_phone)}")
            await make_caretaker_call_batch(alert_by_phone)
        return True
    except Exception as e:
        logger.error(f"Error processing missed calls: {e}")
        session.rollback()
    finally:
        session.close()

from starlette.middleware.sessions import SessionMiddleware

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation exceptions."""
    logger.error(
        f"Validation Exception: {exc.errors} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Client: {request.client.host}"
    )
    user_message = exc.errors()[0].get("msg", "Invalid input data")
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "message": user_message,
            "detail": exc.errors()  # Full details for debugging
        }
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f"Server Exception: {exc} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Client: {request.client.host}"
    )
    logger.exception("Error processing payload")
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc)
        }
    )

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(
        f"HTTP Exception: {exc.detail} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Client: {request.client.host}"
    )
    # logger.exception("Error processing payload")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "detail": str(exc)
        }
    )


@app.get("/celery/tasks/")
async def list_tasks():
    inspector = Inspect(app=celery_app)

    active = inspector.active()
    reserved = inspector.reserved()
    scheduled = inspector.scheduled()

    return {
        "active": active or {},
        "reserved": reserved or {},
        "scheduled": scheduled or {}
    }

# Include API routers
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])
app.include_router(authentication.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(organization.router, prefix="/api/v1/organizations", tags=["Organizations"])
app.include_router(ingest_onboarding_users.router, prefix="/api/v1/admin", tags=["Management"])
app.include_router(call_queues.router, prefix="/api/v1/admin", tags=["Management"])
app.include_router(social.router, prefix="/api/v1/social", tags=["Social"])
app.include_router(brain_coach.router, prefix="/api/v1/brain-coach", tags=["Brain Coach"])
app.include_router(medication.router, prefix="/api/v1/medications", tags=["Medications"])
app.include_router(fall_detection.router, prefix="/api/v1/fall-detection", tags=["Fall Detection"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["Text-to-Speech"])
app.include_router(symptom_checker.router, prefix="/api/v1/symptoms", tags=["Symptoms Checker"])
app.include_router(post_call.router, prefix="/api/v1/post-call", tags=["Post Call"])
app.include_router(ai_assistant.router, prefix="/api/v1/ai-assistant", tags=["AI Assistant"])
app.include_router(news.router, prefix="/api/v1/news", tags=["News"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["Tools"])
app.include_router(twilio.router, prefix="/api/v1/twilio", tags=["Twilio"])

if __name__ == "__main__":
    import uvicorn
    
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 
