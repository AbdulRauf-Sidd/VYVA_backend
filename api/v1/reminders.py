from fastapi import APIRouter, Body, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from pydantic import BaseModel
from datetime import datetime, timezone
from typing import Optional

from core.database import get_async_session
from models.user_check_ins import ScheduledSession, CheckInType
from celery_app import celery_app

import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class ReminderCreate(BaseModel):
    user_id: int
    phone_number: str
    reminder_purpose: str
    scheduled_at: datetime
    metadata: Optional[dict] = None


class ReminderUpdate(BaseModel):
    phone_number: Optional[str] = None
    reminder_purpose: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    metadata: Optional[dict] = None


def _serialize(s: ScheduledSession) -> dict:
    meta = s.session_metadata or {}
    return {
        "id": s.id,
        "user_id": s.user_id,
        "phone_number": meta.get("phone_number"),
        "reminder_purpose": meta.get("reminder_purpose"),
        "scheduled_at": s.scheduled_at,
        "task_id": s.task_id,
        "status": s.status,
        "is_completed": s.is_completed,
        "metadata": meta,
        "created_at": s.created_at,
    }


@router.post("/")
async def create_reminder(payload: ReminderCreate = Body(...)):
    try:
        async with get_async_session() as session:
            meta = {"phone_number": payload.phone_number, "reminder_purpose": payload.reminder_purpose}
            if payload.metadata:
                meta.update(payload.metadata)

            scheduled_session = ScheduledSession(
                session_type=CheckInType.general_reminder.value,
                user_id=payload.user_id,
                scheduled_at=payload.scheduled_at,
                status="pending",
                session_metadata=meta,
            )
            session.add(scheduled_session)
            await session.flush()

            try:
                task = celery_app.send_task(
                    "initiate_general_reminder_call",
                    args=[scheduled_session.id],
                    eta=payload.scheduled_at,
                )
                scheduled_session.task_id = task.id
            except Exception as e:
                logger.error(f"Failed to schedule Celery task for reminder (user {payload.user_id}): {e}")
                raise HTTPException(status_code=500, detail="Failed to schedule reminder task")

            await session.commit()
            await session.refresh(scheduled_session)

            logger.info(f"Created general reminder session {scheduled_session.id} for user {payload.user_id}, task {scheduled_session.task_id}")
            return _serialize(scheduled_session)

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error creating reminder for user {payload.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error while creating reminder")
    except Exception as e:
        logger.error(f"Unexpected error creating reminder for user {payload.user_id}: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error while creating reminder")


@router.get("/")
async def get_upcoming_reminders(user_id: int):
    try:
        async with get_async_session() as session:
            now = datetime.now(timezone.utc)
            result = await session.execute(
                select(ScheduledSession)
                .where(
                    ScheduledSession.user_id == user_id,
                    ScheduledSession.session_type == CheckInType.general_reminder.value,
                    ScheduledSession.scheduled_at > now,
                    ScheduledSession.is_completed == False,
                )
                .order_by(ScheduledSession.scheduled_at.asc())
            )
            sessions = result.scalars().all()
            return [_serialize(s) for s in sessions]

    except SQLAlchemyError as e:
        logger.error(f"Database error fetching reminders for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error while fetching reminders")
    except Exception as e:
        logger.error(f"Unexpected error fetching reminders for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error while fetching reminders")


@router.put("/{reminder_id}")
async def update_reminder(reminder_id: int, payload: ReminderUpdate = Body(...)):
    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(ScheduledSession).where(
                    ScheduledSession.id == reminder_id,
                    ScheduledSession.session_type == CheckInType.general_reminder.value,
                )
            )
            scheduled_session = result.scalars().first()

            if not scheduled_session:
                raise HTTPException(status_code=404, detail="Reminder not found")

            if scheduled_session.is_completed:
                raise HTTPException(status_code=400, detail="Cannot update a completed reminder")

            if scheduled_session.task_id:
                try:
                    celery_app.control.revoke(scheduled_session.task_id, terminate=True)
                    logger.info(f"Revoked Celery task {scheduled_session.task_id} for reminder {reminder_id}")
                except Exception as e:
                    logger.warning(f"Could not revoke Celery task {scheduled_session.task_id}: {e}")

            meta = dict(scheduled_session.session_metadata or {})
            if payload.phone_number is not None:
                meta["phone_number"] = payload.phone_number
            if payload.reminder_purpose is not None:
                meta["reminder_purpose"] = payload.reminder_purpose
            if payload.metadata is not None:
                meta.update(payload.metadata)
            scheduled_session.session_metadata = meta

            if payload.scheduled_at is not None:
                scheduled_session.scheduled_at = payload.scheduled_at

            try:
                task = celery_app.send_task(
                    "initiate_general_reminder_call",
                    args=[scheduled_session.id],
                    eta=scheduled_session.scheduled_at,
                )
                scheduled_session.task_id = task.id
                scheduled_session.status = "pending"
            except Exception as e:
                logger.error(f"Failed to reschedule Celery task for reminder {reminder_id}: {e}")
                raise HTTPException(status_code=500, detail="Failed to reschedule reminder task")

            await session.commit()
            await session.refresh(scheduled_session)

            logger.info(f"Updated reminder {reminder_id}, new task {scheduled_session.task_id}")
            return _serialize(scheduled_session)

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error updating reminder {reminder_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error while updating reminder")
    except Exception as e:
        logger.error(f"Unexpected error updating reminder {reminder_id}: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error while updating reminder")


@router.delete("/{reminder_id}")
async def delete_reminder(reminder_id: int):
    try:
        async with get_async_session() as session:
            result = await session.execute(
                select(ScheduledSession).where(
                    ScheduledSession.id == reminder_id,
                    ScheduledSession.session_type == CheckInType.general_reminder.value,
                )
            )
            scheduled_session = result.scalars().first()

            if not scheduled_session:
                raise HTTPException(status_code=404, detail="Reminder not found")

            if scheduled_session.task_id and not scheduled_session.is_completed:
                try:
                    celery_app.control.revoke(scheduled_session.task_id, terminate=True)
                    logger.info(f"Revoked Celery task {scheduled_session.task_id} for reminder {reminder_id}")
                except Exception as e:
                    logger.warning(f"Could not revoke Celery task {scheduled_session.task_id}: {e}")

            await session.delete(scheduled_session)
            await session.commit()

            logger.info(f"Deleted reminder {reminder_id}")
            return {"message": "Reminder deleted successfully"}

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error deleting reminder {reminder_id}: {e}")
        raise HTTPException(status_code=500, detail="Database error while deleting reminder")
    except Exception as e:
        logger.error(f"Unexpected error deleting reminder {reminder_id}: {e}")
        raise HTTPException(status_code=500, detail="Unexpected error while deleting reminder")
