"""
Vyva Backend - FastAPI Application Entry Point

A production-ready FastAPI backend for senior care applications.
"""

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
from apscheduler.triggers.interval import IntervalTrigger
from fastapi.exceptions import RequestValidationError

from core.config import settings
from core.logging import setup_logging
from core.database import engine, Base
from api.v1 import onboarding, users, profiles, health_care, social, brain_coach, medication, fall_detection, emergency, tts, symptom_checker, post_call, ai_assistant, news, tools, organization, authentication
from api.v1.managemant import ingest_onboarding_users
from apscheduler.schedulers.background import BackgroundScheduler
# from tasks import check_medication_time, run_async_job
from core.database import AsyncSessionLocal, get_db
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
from repositories.medication import MedicationRepository
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from celery import chain
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
from celery.app.control import Inspect
from celery_app import celery_app
from fastmcp import FastMCP

# Setup logging
logger = setup_logging()

mcp = FastMCP("Memory Tools")
mcp_app = mcp.http_app('/mcp')


# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     """Application lifespan events."""
#     # Startup
#     logger.info("Starting Vyva Backend application...")
    
#     # Create database tables (for development)
#     if settings.ENV == "development":
#         async with engine.begin() as conn:
#             await conn.run_sync(Base.metadata.create_all)
#         logger.info("Database tables created (development mode)")


#     # if not scheduler.running:
#     #     scheduler.add_job(
#     #         minute_background_task,
#     #         trigger=IntervalTrigger(seconds=60),
#     #         id="minute_task",
#     #         name="Run every minute",
#     #         replace_existing=True
#     #     )
#     #     scheduler.start()
#     #     logger.info("Background task scheduler started")
    
#     yield
    
#     # Shutdown
#     logger.info("Shutting down Vyva Backend application...")


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

app.mount("", mcp_app)

@app.middleware("http")
async def middleware(request, call_next):
    if request.url.path.startswith("/mcp"):
        return await call_next(request)
    # REST-only logic

scheduler = AsyncIOScheduler()


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
                run_time = datetime.now() + timedelta(minutes=3)
                scheduler.add_job(process_missed_calls, trigger=DateTrigger(run_date=run_time), args=[batch_id])
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
    allow_origins=settings.origins,  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Allow all hosts for development
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
        f"Server Exception: {exc.detail} | "
        f"Path: {request.url.path} | "
        f"Method: {request.method} | "
        f"Client: {request.client.host}"
    )
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
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "message": exc.detail,
            "detail": str(exc)
        }
    )


@app.get("/admin/celery/tasks/")
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
# app.include_router(authen.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(users.router, prefix="/api/v1/users", tags=["Users"])
app.include_router(onboarding.router, prefix="/api/v1/onboarding", tags=["Onboarding"])
app.include_router(authentication.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(organization.router, prefix="/api/v1/organizations", tags=["Organizations"])
app.include_router(ingest_onboarding_users.router, prefix="/api/v1/admin", tags=["Management"])
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
app.include_router(ai_assistant.router, prefix="/api/v1/ai-assistant", tags=["AI Assistant"])
app.include_router(news.router, prefix="/api/v1/news", tags=["News"])
app.include_router(tools.router, prefix="/api/v1/tools", tags=["Tools"])
app.include_router(emergency.router, prefix="/api/v1/emergency", tags=["Emergency Contacts"])

class MathInput(BaseModel):
    a: float
    b: float

@mcp.tool(
    name="math_operations",
    description="Performs math operations on two numbers"
)
def math_operations(input: MathInput):
    return {
        "result": input.a * input.b * 1237213712 // 1232
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 