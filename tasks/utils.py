from celery_app import celery_app
from core.redis import conn, ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY, MEDICATION_REMINDER_CALL_STATUS_CHECK_REDIS_KEY
from models.medication import MedicationLog
import logging
from core.database import SessionLocal
from models.user_check_ins import ScheduledSession, UserCheckin, CheckInType
from sqlalchemy.orm import selectinload
from sqlalchemy import desc
from datetime import datetime, date, time
from scripts.utils import convert_to_utc_datetime

logger = logging.getLogger(__name__)

def schedule_reminder_message(payload, dt_utc, preferred_reminder_channel):
    if preferred_reminder_channel:
        if preferred_reminder_channel == "whatsapp":
            celery_app.send_task(
                "send_whatsapp_medication_reminder",
                args=[payload,],
                eta=dt_utc
            )
        elif preferred_reminder_channel == "phone":
            celery_app.send_task(
                "initiate_medication_reminder_call",
                args=[payload,],
                eta=dt_utc
            )
        elif preferred_reminder_channel == "app":
            celery_app.send_task(
                "send_app_medication_reminder",
                args=[payload,],
                eta=dt_utc
            )
        else:
            # Default to WhatsApp
            celery_app.send_task(
                "send_whatsapp_medication_reminder",
                args=[payload,],
                eta=dt_utc
            )


def schedule_celery_task_for_call_status_check(payload=None):
    if payload:
        exists = conn.get(MEDICATION_REMINDER_CALL_STATUS_CHECK_REDIS_KEY)
        if not exists:
            celery_app.send_task(
                "update_call_status",
                args=[payload,],
                countdown=300 # 5 minutes
            )
            conn.set(MEDICATION_REMINDER_CALL_STATUS_CHECK_REDIS_KEY, 1, ex=300)    
    else:
        exists = conn.get(ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY)
    if not exists:
        celery_app.send_task(
            "check_onboarding_call_status",
            countdown=300  # 5 minutes
        )
        conn.set(ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY, 1, ex=300)  # Key expires in 5 minutes


def update_medication_status(payload, status):
    db = SessionLocal()
    try:
        medications = payload.get('medications')
        for medication in medications:
            medication_log = MedicationLog(
                user_id=payload.get('user_id'), 
                medication_id = medication.get('medication_id'),
                medication_time_id = medication.get('time_id'),
                status=status,
            )

            db.add(medication_log)
        
        db.commit()
    except Exception as e:
        logger.error(f"error marking medication as missed: {e}")
    finally:
        db.close()

def schedule_check_in_calls_for_day(db, today): #TODO can implement checks so that only one type of check in can exist in a day 
    try:
        checkins = (
            db.query(UserCheckin)
            .options(selectinload(UserCheckin.user),
                     selectinload(UserCheckin.scheduled_sessions))
            .filter(UserCheckin.is_active == True)
            .all()
        )

        scheduled_count = 0

        for checkin in checkins:
            try:
                # --- get last scheduled session ---
                last_session = max(
                    checkin.scheduled_sessions,
                    key=lambda s: s.scheduled_at,
                    default=None
                )

                should_schedule = False

                if not last_session:
                    should_schedule = True
                else:
                    days_since = (today - last_session.scheduled_at.date()).days
                    if days_since >= checkin.check_in_frequency_days:
                        should_schedule = True

                if not should_schedule:
                    continue

                # --- compute schedule time ---
                check_time = checkin.check_in_time
                if not check_time:
                    check_time = get_default_time_obj(check_in_type=checkin.check_in_type)  # default to 12 PM if no time set
                

                scheduled_dt = convert_to_utc_datetime(tz_name=checkin.user.timezone, date=today, time=check_time)
                if checkin.check_in_type == CheckInType.brain_coach.value:
                    task_name = "initiate_brain_coach_session"
                elif checkin.check_in_type == CheckInType.check_up_call.value:
                    task_name = "initiate_check_up_call"
                else:
                    logger.warning(f"Unknown check-in type for check-in {checkin.id}, skipping scheduling.")
                    continue

                # --- call scheduler ---
                task_id = celery_app.send_task(
                    task_name,
                    args=[checkin.id,],
                    # eta=scheduled_dt
                ).id

                # --- create scheduled session row ---
                new_session = ScheduledSession(
                    session_type=checkin.check_in_type,
                    scheduled_at=scheduled_dt,
                    user_checkin_id=checkin.id,
                    is_completed=False,
                    task_id=task_id
                )

                db.add(new_session)
                scheduled_count += 1

            except Exception as e:
                logger.error(f"Error processing checkin {checkin.id}: {e}")
                continue

        db.commit()
        logger.info(f"Scheduled {scheduled_count} check-in sessions")

    except Exception as e:
        db.rollback()
        logger.error(f"Scheduler failure: {e}")


def get_default_time_obj(check_in_type = None):
    if not check_in_type:
        return time(hour=12, minute=0)  # default to 12 PM if no time set
    if check_in_type == CheckInType.brain_coach.value:
        return time(hour=15, minute=0)  # default to 3 PM for brain coach
    if check_in_type == CheckInType.check_up_call.value:
        return time(hour=10, minute=0)  # default to 10 AM for check up call