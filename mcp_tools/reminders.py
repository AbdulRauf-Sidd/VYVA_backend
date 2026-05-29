from .mcp_instance import mcp
from sqlalchemy import select
from pydantic import BaseModel
from core.database import get_async_session
from models.user import User
from models.user_check_ins import ScheduledSession, CheckInType
from celery_app import celery_app
from scripts.utils import get_zoneinfo_safe
from datetime import datetime
from zoneinfo import ZoneInfo

import logging

logger = logging.getLogger(__name__)


class CreateGeneralReminderInput(BaseModel):
    user_id: int
    reminder_purpose: str
    scheduled_at: str  # ISO datetime string in the user's local time (e.g. "2026-05-27T15:00:00")


@mcp.tool(
    name="create_general_reminder",
    description=(
        "Use this tool when the user asks to set a reminder or be called back at a specific time. "
        "The reminder will trigger an outbound call to the user at the scheduled time. "
        "Provide the user_id, a clear reminder_purpose describing what the reminder is for, "
        "and scheduled_at as an ISO datetime string in the user's LOCAL time (e.g. '2026-05-27T15:00:00'). "
        "Do NOT convert to UTC — pass the local time as-is; the system handles timezone conversion. "
        "Examples of when to use: 'remind me to call my doctor tomorrow at 2pm', "
        "'set a reminder for my physiotherapy appointment on Friday at 10am', "
        "'call me tonight at 8 to remind me to take my evening pills'."
    )
)
async def create_general_reminder(input: CreateGeneralReminderInput) -> dict:
    try:
        async with get_async_session() as db:
            result = await db.execute(select(User).where(User.id == input.user_id))
            user = result.scalars().first()

            if not user:
                return {"success": False, "message": "User not found."}

            if not user.phone_number:
                return {"success": False, "message": "User has no phone number on file."}

            tz = get_zoneinfo_safe(user.timezone)
            local_dt = datetime.fromisoformat(input.scheduled_at)
            if local_dt.tzinfo is None:
                local_dt = local_dt.replace(tzinfo=tz)
            scheduled_at_utc = local_dt.astimezone(ZoneInfo("UTC"))

            now_utc = datetime.now(ZoneInfo("UTC"))
            if scheduled_at_utc <= now_utc:
                return {"success": False, "message": "Scheduled time must be in the future."}

            meta = {
                "phone_number": user.phone_number,
                "reminder_purpose": input.reminder_purpose,
            }

            scheduled_session = ScheduledSession(
                session_type=CheckInType.general_reminder.value,
                user_id=user.id,
                scheduled_at=scheduled_at_utc,
                status="pending",
                session_metadata=meta,
            )
            db.add(scheduled_session)
            await db.flush()

            task = celery_app.send_task(
                "initiate_general_reminder_call",
                args=[scheduled_session.id],
                eta=scheduled_at_utc,
            )
            scheduled_session.task_id = task.id

            await db.commit()

            logger.info(
                f"MCP: created general reminder session {scheduled_session.id} "
                f"for user {user.id} at {scheduled_at_utc} (task {task.id})"
            )

            return {
                "success": True,
                "reminder_id": scheduled_session.id,
                "scheduled_at_utc": scheduled_at_utc.isoformat(),
                "reminder_purpose": input.reminder_purpose,
            }

    except Exception as e:
        logger.error(f"MCP create_general_reminder failed for user {input.user_id}: {e}")
        return {"success": False, "message": "Failed to create reminder."}


class GetUpcomingRemindersInput(BaseModel):
    user_id: int


@mcp.tool(
    name="get_upcoming_reminders",
    description=(
        "Use this tool to retrieve all upcoming (future, not yet completed) general reminders for a user. "
        "Returns a list of reminders with their ID, purpose, scheduled time, and status. "
        "Use this when the user asks what reminders they have set, or before updating/deleting one."
    )
)
async def get_upcoming_reminders(input: GetUpcomingRemindersInput) -> dict:
    try:
        async with get_async_session() as db:
            user_result = await db.execute(select(User).where(User.id == input.user_id))
            user = user_result.scalars().first()

            if not user:
                return {"success": False, "message": "User not found."}

            tz = get_zoneinfo_safe(user.timezone)
            now_utc = datetime.now(ZoneInfo("UTC"))

            result = await db.execute(
                select(ScheduledSession)
                .where(
                    ScheduledSession.user_id == input.user_id,
                    ScheduledSession.session_type == CheckInType.general_reminder.value,
                    ScheduledSession.scheduled_at > now_utc,
                    ScheduledSession.is_completed == False,
                )
                .order_by(ScheduledSession.scheduled_at.asc())
            )
            sessions = result.scalars().all()

            reminders = []
            for s in sessions:
                meta = s.session_metadata or {}
                local_dt = s.scheduled_at.astimezone(tz)
                reminders.append({
                    "reminder_id": s.id,
                    "reminder_purpose": meta.get("reminder_purpose"),
                    "scheduled_at_local": local_dt.strftime("%Y-%m-%d %H:%M %Z"),
                    "status": s.status,
                })

            return {"success": True, "reminders": reminders}

    except Exception as e:
        logger.error(f"MCP get_upcoming_reminders failed for user {input.user_id}: {e}")
        return {"success": False, "message": "Failed to fetch reminders."}


class UpdateGeneralReminderInput(BaseModel):
    reminder_id: int
    reminder_purpose: str | None = None
    scheduled_at: str | None = None  # ISO datetime string in the user's local time


@mcp.tool(
    name="update_general_reminder",
    description=(
        "Use this tool when the user wants to change an existing reminder's purpose or scheduled time. "
        "Provide the reminder_id (get it from get_upcoming_reminders if the user doesn't know it). "
        "Pass only the fields that need to change — omit fields that should stay the same. "
        "scheduled_at must be an ISO datetime string in the user's LOCAL time if provided. "
        "The previous call will be automatically cancelled and rescheduled."
    )
)
async def update_general_reminder(input: UpdateGeneralReminderInput) -> dict:
    try:
        async with get_async_session() as db:
            result = await db.execute(
                select(ScheduledSession).where(
                    ScheduledSession.id == input.reminder_id,
                    ScheduledSession.session_type == CheckInType.general_reminder.value,
                )
            )
            session = result.scalars().first()

            if not session:
                return {"success": False, "message": "Reminder not found."}

            if session.is_completed:
                return {"success": False, "message": "Cannot update a completed reminder."}

            if session.task_id:
                try:
                    celery_app.control.revoke(session.task_id, terminate=True)
                    logger.info(f"MCP: revoked task {session.task_id} for reminder {input.reminder_id}")
                except Exception as e:
                    logger.warning(f"MCP: could not revoke task {session.task_id}: {e}")

            meta = dict(session.session_metadata or {})

            if input.reminder_purpose is not None:
                meta["reminder_purpose"] = input.reminder_purpose
                session.session_metadata = meta

            if input.scheduled_at is not None:
                user_result = await db.execute(select(User).where(User.id == session.user_id))
                user = user_result.scalars().first()
                tz = get_zoneinfo_safe(user.timezone if user else None)
                local_dt = datetime.fromisoformat(input.scheduled_at)
                if local_dt.tzinfo is None:
                    local_dt = local_dt.replace(tzinfo=tz)
                new_utc = local_dt.astimezone(ZoneInfo("UTC"))
                now_utc = datetime.now(ZoneInfo("UTC"))
                if new_utc <= now_utc:
                    return {"success": False, "message": "Scheduled time must be in the future."}
                session.scheduled_at = new_utc

            task = celery_app.send_task(
                "initiate_general_reminder_call",
                args=[session.id],
                eta=session.scheduled_at,
            )
            session.task_id = task.id
            session.status = "pending"

            await db.commit()

            logger.info(f"MCP: updated reminder {input.reminder_id}, new task {task.id}")
            return {
                "success": True,
                "reminder_id": session.id,
                "reminder_purpose": meta.get("reminder_purpose"),
                "scheduled_at_utc": session.scheduled_at.isoformat(),
            }

    except Exception as e:
        logger.error(f"MCP update_general_reminder failed for reminder {input.reminder_id}: {e}")
        return {"success": False, "message": "Failed to update reminder."}


class DeleteGeneralReminderInput(BaseModel):
    reminder_id: int


@mcp.tool(
    name="delete_general_reminder",
    description=(
        "Use this tool when the user wants to cancel or delete an existing reminder. "
        "Provide the reminder_id (get it from get_upcoming_reminders if the user doesn't know it). "
        "The scheduled call will be cancelled and the reminder permanently removed."
    )
)
async def delete_general_reminder(input: DeleteGeneralReminderInput) -> dict:
    try:
        async with get_async_session() as db:
            result = await db.execute(
                select(ScheduledSession).where(
                    ScheduledSession.id == input.reminder_id,
                    ScheduledSession.session_type == CheckInType.general_reminder.value,
                )
            )
            session = result.scalars().first()

            if not session:
                return {"success": False, "message": "Reminder not found."}

            if session.task_id and not session.is_completed:
                try:
                    celery_app.control.revoke(session.task_id, terminate=True)
                    logger.info(f"MCP: revoked task {session.task_id} for reminder {input.reminder_id}")
                except Exception as e:
                    logger.warning(f"MCP: could not revoke task {session.task_id}: {e}")

            await db.delete(session)
            await db.commit()

            logger.info(f"MCP: deleted reminder {input.reminder_id}")
            return {"success": True, "message": "Reminder cancelled and deleted."}

    except Exception as e:
        logger.error(f"MCP delete_general_reminder failed for reminder {input.reminder_id}: {e}")
        return {"success": False, "message": "Failed to delete reminder."}
