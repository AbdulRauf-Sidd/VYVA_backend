"""
Vyva Backend - FastAPI Application Entry Point

A production-ready FastAPI backend for senior care applications.
"""

import os
import time
import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, Response, status, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from apscheduler.triggers.interval import IntervalTrigger
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from core.config import settings
from core.logging import setup_logging
from core.database import engine, Base
from api.v1 import auth, users, profiles, health_care, social, brain_coach, medication, fall_detection, emergency, tts, symptom_checker, post_call
import subprocess
from apscheduler.schedulers.background import BackgroundScheduler
# from tasks import check_medication_time, run_async_job
from core.database import AsyncSessionLocal, get_db
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from repositories.medication import MedicationRepository
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from celery import chain
from tasks import process_medication_reminders
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from services.elevenlabs_service import make_reminder_call_batch, check_batch_for_missed, make_caretaker_call_batch
from services.helpers import construct_whatsapp_sms_message, construct_sms_body_from_template_for_reminders
from services.whatsapp_service import whatsapp
from services.email_service import email_service
from schemas.eleven_labs_batch_calls import ElevenLabsBatchCallCreate
from repositories.eleven_labs_batch_calls import ElevenLabsBatchCallRepository
from repositories.user import UserRepository
from apscheduler.triggers.date import DateTrigger




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


    if not scheduler.running:
        scheduler.add_job(
            minute_background_task,
            trigger=IntervalTrigger(seconds=60),
            id="minute_task",
            name="Run every minute",
            replace_existing=True
        )
        scheduler.start()
        logger.info("Background task scheduler started")
    
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


scheduler = AsyncIOScheduler()


async def process_missed_calls(batch_id):
    logger(f"Proccessing missed calls for batch {batch_id}")
    phone_number_set = check_batch_for_missed(batch_id=batch_id)
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





async def minute_background_task():
    """Background task that runs every minute and has database access"""
    # Create a new session for this background task
    session = AsyncSessionLocal()
    try:
        current_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        cet_time = current_time.astimezone(ZoneInfo("Europe/Berlin")).time() 
        print('current_time', cet_time)
        logger.info(f"Processing medication reminders for users at {cet_time}")
        medication_repo = MedicationRepository(session)
        user_list = await medication_repo.get_active_medications_with_times()

        logger.info(f"User list: {user_list}")

        call_users = []

        if user_list:
            logger.info(f"Number of Users for medication call: {len(user_list)}")
            # Option 1a: Chain tasks (runs sequentially)
            for user in user_list:
                if user['preferred_channel'] == 'sms':
                    logger.info(f"Sending SMS to user {user['user_id']} for medication {user['medications']} at {current_time}")
                    content = construct_whatsapp_sms_message(user)
                    body = construct_sms_body_from_template_for_reminders(content, language='es')
                    await whatsapp.send_sms(user['phone_number'], body)
                    continue
                elif user['preferred_channel'] == 'email':
                    logger.info(f"Sending Email to user {user['user_id']} for medication {user['medications']} at {current_time}")
                    await email_service.send_medication_reminder(user, language='es')
                    continue
                elif user['preferred_channel'] == 'phone':
                    call_users.append(user)
                    continue
                elif user['preferred_channel'] == 'whatsapp':
                    logger.info(f"Sending WhatsApp message to user {user['user_id']} for medication {user['medications']} at {current_time}")
                    content = construct_whatsapp_sms_message(user)
                    await whatsapp.send_reminder_message(user['phone_number'], content)
                    continue

                else:
                    logger.error(f"Unknown channel for user {user['user_id']}.")
                    continue

        if call_users:
            logger.info(f"Making Batch calls for {len(call_users)} users at {current_time}")
            batch_id = await make_reminder_call_batch(call_users)
            if batch_id:
                run_time = datetime.now() + timedelta(minutes=5)
                scheduler.add_job(process_missed_calls(batch_id), trigger=DateTrigger(run_date=run_time))
                logger.info(f"Job scheduled for missed calls with batch id {batch_id}")


            try:
                param = ElevenLabsBatchCallCreate(
                    batch_id=batch_id
                )
                batch_repo = ElevenLabsBatchCallRepository(session)
                await batch_repo.create(param)
            except Exception as e:
                logger.info(f"Error occured while making record for batch: {e}")

        else:
            logger.info("No users found for medication call at this time.")

        return {"found_users": len(user_list)}

    except Exception as e:
        print(f"Error in background task: {e}")
        # Rollback in case of error
        await session.rollback()
    finally:
        # Always close the session
        await session.close()


# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Allow all hosts for development
)

# Request/response logging middleware removed to prevent body parsing issues


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



# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["Profiles"])
app.include_router(health_care.router, prefix="/api/v1/health-care", tags=["Health & Care"])
app.include_router(social.router, prefix="/api/v1/social", tags=["Social"])
app.include_router(brain_coach.router, prefix="/api/v1/brain-coach", tags=["Brain Coach"])
app.include_router(medication.router, prefix="/api/v1/medications", tags=["Medications"])
app.include_router(fall_detection.router, prefix="/api/v1/fall-detection", tags=["Fall Detection"])
app.include_router(emergency.router, prefix="/api/v1/emergency", tags=["Emergency Contacts"])
app.include_router(tts.router, prefix="/api/v1/tts", tags=["Text-to-Speech"])
app.include_router(symptom_checker.router, prefix="/api/v1/symptoms", tags=["Symptoms Checker"])
app.include_router(post_call.router, prefix="/api/v1/post-call", tags=["Post Call"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 