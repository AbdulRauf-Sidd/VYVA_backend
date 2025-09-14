from celery_app import celery_app
import time
import random
from repositories.user import UserRepository
from datetime import datetime
from celery import chain, group
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
import asyncio
from fastapi import BackgroundTasks
# from fastapi_utils.tasks import repeat_every

logger = logging.getLogger(__name__)


# def run_async_job():
#     logger.info("Running async job from sync context")
#     """Synchronous wrapper that runs the async function"""
#     asyncio.run(check_medication_time())

# @celery_app.task(bind=True)
# @app.on_event("startup")
# @repeat_every(seconds=60)
# async def check_medication_time(self):
#     async with get_db() as db_session:
#         current_time = datetime.now().time().replace(second=0, microsecond=0)
#         print('current_time', current_time)
#         logger.info(f"Processing medication reminders for users at {current_time}")
#         user_repo = UserRepository(db_session)
#         user_list = await user_repo.get_active_users_with_medication_times()
#         users_for_medication_call = []
#         for user in user_list:
#             user_id = user.id
#             medications = user.medications
#             for medication in medications:
#                 medication_id = medication.id
#                 for time_entry in medication.times_of_day:
#                     if time_entry.time_of_day == current_time:
#                         logger.info(f"User {user_id} has medication {medication_id} scheduled at {current_time}")
#                         users_for_medication_call.append({'user_id': user_id, 'medication_id': medication_id, 'time_of_day': time_entry.time_of_day, 'notes': time_entry.notes})

#         if users_for_medication_call:
#             logger.info(f"Number of Users for medication call: {len(users_for_medication_call)}")
#             # Option 1a: Chain tasks (runs sequentially)
#             chain(
#                 process_medication_reminders.s(users_for_medication_call)
#             ).apply_async()

#         else:
#             logger.info("No users found for medication call at this time.")

#         return {"found_users": len(users_for_medication_call)}

@celery_app.task(bind=True)
def process_medication_reminders(self, users_for_medication_call):
    current_time = datetime.now().time().replace(second=0, microsecond=0)

    for user in users_for_medication_call:
        if user.channel == 'sms':
            # Simulate sending SMS
            logger.info(f"Sending SMS to user {user['user_id']} for medication {user['medication_id']} at {current_time}")

        elif user.channel == 'email':
            # Simulate sending Email
            logger.info(f"Sending Email to user {user['user_id']} for medication {user['medication_id']} at {current_time}")
        elif user.channel == 'phone':
            # Simulate making a phone call
            logger.info(f"Making Phone Call to user {user['user_id']} for medication {user['medication_id']} at {current_time}")
        elif user.channel == 'whatsapp':
            # Simulate sending WhatsApp message
            logger.info(f"Sending WhatsApp message to user {user['user_id']} for medication {user['medication_id']} at {current_time}")
        else:
            logger.error(f"Unknown channel for user {user['user_id']}.")
            continue


@celery_app.task(
    bind=True,
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=600,  # Max 10 minutes delay
    retry_jitter=True      # Add randomness to retry timing
)
def process_medication_reminders(self, users_for_medication_call):
    current_time = datetime.now().time().replace(second=0, microsecond=0)

    for user in users_for_medication_call:
        if user.channel == 'sms':
            # Simulate sending SMS
            logger.info(f"Sending SMS to user {user['user_id']} for medication {user['medication_id']} at {current_time}")
            
        elif user.channel == 'email':
            # Simulate sending Email
            logger.info(f"Sending Email to user {user['user_id']} for medication {user['medication_id']} at {current_time}")
        elif user.channel == 'phone':
            # Simulate making a phone call
            logger.info(f"Making Phone Call to user {user['user_id']} for medication {user['medication_id']} at {current_time}")
        elif user.channel == 'whatsapp':
            # Simulate sending WhatsApp message
            logger.info(f"Sending WhatsApp message to user {user['user_id']} for medication {user['medication_id']} at {current_time}")
        else:
            logger.error(f"Unknown channel for user {user['user_id']}.")
            continue


