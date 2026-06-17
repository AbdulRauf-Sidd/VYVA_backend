import logging
from datetime import datetime, timezone
from typing import List

from pydantic import BaseModel
from sqlalchemy import select

from datetime import date
from typing import Optional

from celery_app import celery_app
from core.database import get_async_session
from models.user import User
from models.user_check_ins import CheckInType, ScheduledSession
from models.outbound_call_logs import OutboundCallLog
from models.organization import OrganizationAgents
from scripts.utils import convert_to_utc_datetime, get_zoneinfo_safe
from .mcp_instance import mcp

logger = logging.getLogger(__name__)

SESSION_TYPE = CheckInType.general_reminders.value


# ── Pydantic models ────────────────────────────────────────────────────────────

class CreateGeneralReminderInput(BaseModel):
    user_id: int
    purpose: str
    datetime_str: str


class GetGeneralRemindersInput(BaseModel):
    user_id: int
    status: str  # "pending" | "cancelled" | "completed"


class UpdateGeneralReminderInput(BaseModel):
    user_id: int
    scheduled_session_id: int
    datetime_str: str


class DeleteGeneralReminderInput(BaseModel):
    user_id: int
    scheduled_session_id: int


# ── Helpers ───────────────────────────────────────────────────────────────────

def _parse_local_dt(datetime_str: str) -> datetime:
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(datetime_str.strip(), fmt)
        except ValueError:
            continue
    raise ValueError(
        f"Cannot parse datetime '{datetime_str}'. Expected format: YYYY-MM-DD HH:MM"
    )


def _session_to_dict(session: ScheduledSession) -> dict:
    metadata = session.metadata_ or {}
    return {
        "id": session.id,
        "purpose": metadata.get("purpose"),
        "scheduled_at_utc": session.scheduled_at.isoformat() if session.scheduled_at else None,
        "is_completed": session.is_completed,
        "is_cancelled": session.is_cancelled,
        "created_at": session.created_at.isoformat() if session.created_at else None,
    }


# ── Tools ─────────────────────────────────────────────────────────────────────

# @mcp.tool(
#     name="create_general_reminder",
#     description=(
#         "Schedule a one-time reminder for a user about anything they want. "
#         "Do not use this tool for medication reminders or check-up calls, as there are separate tools for those. "
#         "Provide the reminder date and time in the user's local timezone "
#         "using a format like '2025-06-01 14:30'. "
#         "The scheduled time must be in the future. "
#         "Returns the reminder ID on success."
#     ),
# )
# async def create_general_reminder(input: CreateGeneralReminderInput) -> dict:
#     try:
#         async with get_async_session() as db:
#             result = await db.execute(select(User.timezone).where(User.id == input.user_id))
#             user_tz_str = result.scalars().first()
#             if user_tz_str is None:
#                 return {"success": False, "message": f"User {input.user_id} not found."}

#             naive_local = _parse_local_dt(input.datetime_str)

#             utc_dt = convert_to_utc_datetime(tz_name=user_tz_str, dt=naive_local)
#             if utc_dt is None:
#                 return {"success": False, "message": "Failed to convert datetime to UTC."}

#             now_utc = datetime.now(timezone.utc)
#             if utc_dt <= now_utc:
#                 return {
#                     "success": False,
#                     "message": (
#                         f"The reminder time '{input.datetime_str}' is in the past. "
#                         "Please choose a future date and time."
#                     ),
#                 }

#             session_record = ScheduledSession(
#                 session_type=SESSION_TYPE,
#                 scheduled_at=utc_dt,
#                 user_id=input.user_id,
#                 user_checkin_id=None,
#                 is_completed=False,
#                 is_cancelled=False,
#                 metadata_={"purpose": input.purpose},
#             )
#             db.add(session_record)
#             await db.flush()

#             task = celery_app.send_task("fire_general_reminder", args=[session_record.id], eta=utc_dt)
#             session_record.task_id = task.id
#             await db.commit()

#             return {
#                 "success": True,
#                 "scheduled_session_id": session_record.id,
#                 "scheduled_at_utc": utc_dt.isoformat(),
#             }

#     except ValueError as e:
#         return {"success": False, "message": str(e)}
#     except Exception as e:
#         logger.error(f"[create_general_reminder] Error for user {input.user_id}: {e}")
#         return {"success": False, "message": "An unexpected error occurred."}


# @mcp.tool(
#     name="get_general_reminders",
#     description=(
#         "Retrieve a user's general reminders by status. "
#         "Status must be one of: 'pending', 'cancelled', or 'completed'. "
#         "'pending' returns upcoming active reminders, "
#         "'cancelled' returns recently cancelled reminders, "
#         "and 'completed' returns reminders that have already occurred."
#     ),
# )
# async def get_general_reminders(input: GetGeneralRemindersInput) -> List[dict]:
#     try:
#         status = input.status.strip().lower()
#         if status not in ("pending", "cancelled", "completed"):
#             return [{"error": f"Invalid status '{status}'. Must be: pending, cancelled, or completed."}]

#         async with get_async_session() as db:
#             now_utc = datetime.now(timezone.utc)

#             base = select(ScheduledSession).where(
#                 ScheduledSession.user_id == input.user_id,
#                 ScheduledSession.session_type == SESSION_TYPE,
#             )

#             if status == "pending":
#                 stmt = (
#                     base
#                     .where(ScheduledSession.is_cancelled == False, ScheduledSession.scheduled_at > now_utc)  # noqa: E712
#                     .order_by(ScheduledSession.scheduled_at.asc())
#                 )
#             elif status == "cancelled":
#                 stmt = (
#                     base
#                     .where(ScheduledSession.is_cancelled == True)  # noqa: E712
#                     .order_by(ScheduledSession.scheduled_at.desc())
#                     .limit(5)
#                 )
#             else:
#                 stmt = (
#                     base
#                     .where(ScheduledSession.is_cancelled == False, ScheduledSession.scheduled_at < now_utc)  # noqa: E712
#                     .order_by(ScheduledSession.scheduled_at.desc())
#                     .limit(5)
#                 )

#             result = await db.execute(stmt)
#             return [_session_to_dict(s) for s in result.scalars().all()]

#     except Exception as e:
#         logger.error(f"[get_general_reminders] Error for user {input.user_id}: {e}")
#         return [{"error": "An unexpected error occurred."}]


# @mcp.tool(
#     name="update_general_reminder",
#     description=(
#         "Reschedule an existing general reminder to a new future date and time. "
#         "Provide the new date and time in the user's local timezone "
#         "using a format like '2025-06-01 14:30'. "
#         "Returns the updated scheduled UTC time on success."
#     ),
# )
# async def update_general_reminder(input: UpdateGeneralReminderInput) -> dict:
#     try:
#         async with get_async_session() as db:
#             result = await db.execute(
#                 select(ScheduledSession).where(ScheduledSession.id == input.scheduled_session_id)
#             )
#             session_record = result.scalars().first()

#             if not session_record:
#                 return {"success": False, "message": f"Reminder {input.scheduled_session_id} not found."}
#             if session_record.session_type != SESSION_TYPE:
#                 return {"success": False, "message": "This session is not a general reminder."}
#             if session_record.user_id != input.user_id:
#                 return {"success": False, "message": "Permission denied: reminder does not belong to this user."}
#             if session_record.is_cancelled:
#                 return {"success": False, "message": "Cannot reschedule a cancelled reminder."}
#             if session_record.is_completed:
#                 return {"success": False, "message": "Cannot reschedule a reminder that has already fired."}

#             tz_result = await db.execute(select(User.timezone).where(User.id == input.user_id))
#             user_tz_str = tz_result.scalars().first()

#             naive_local = _parse_local_dt(input.datetime_str)
#             new_utc_dt = convert_to_utc_datetime(tz_name=user_tz_str, dt=naive_local)
#             if new_utc_dt is None:
#                 return {"success": False, "message": "Failed to convert datetime to UTC."}

#             now_utc = datetime.now(timezone.utc)
#             if new_utc_dt <= now_utc:
#                 return {
#                     "success": False,
#                     "message": (
#                         f"The new time '{input.datetime_str}' is in the past "
#                         "Please choose a future date and time."
#                     ),
#                 }

#             if session_record.task_id:
#                 try:
#                     celery_app.control.revoke(session_record.task_id, terminate=True)
#                 except Exception as exc:
#                     logger.warning(f"Could not revoke task {session_record.task_id}: {exc}")

#             new_task = celery_app.send_task("fire_general_reminder", args=[session_record.id], eta=new_utc_dt)
#             session_record.scheduled_at = new_utc_dt
#             session_record.task_id = new_task.id
#             await db.commit()

#             return {
#                 "success": True,
#                 "scheduled_session_id": session_record.id,
#                 "new_scheduled_at_utc": new_utc_dt.isoformat(),
#             }

#     except ValueError as e:
#         return {"success": False, "message": str(e)}
#     except Exception as e:
#         logger.error(f"[update_general_reminder] Error for session {input.scheduled_session_id}: {e}")
#         return {"success": False, "message": "An unexpected error occurred."}


# @mcp.tool(
#     name="delete_general_reminder",
#     description=(
#         "Cancel an existing pending general reminder for a user. "
#         "Cancelled reminders are retained for history and can still be retrieved later."
#     ),
# )
# async def delete_general_reminder(input: DeleteGeneralReminderInput) -> dict:
#     try:
#         async with get_async_session() as db:
#             result = await db.execute(
#                 select(ScheduledSession).where(ScheduledSession.id == input.scheduled_session_id)
#             )
#             session_record = result.scalars().first()

#             if not session_record:
#                 return {"success": False, "message": f"Reminder {input.scheduled_session_id} not found."}
#             if session_record.session_type != SESSION_TYPE:
#                 return {"success": False, "message": "This session is not a general reminder."}
#             if session_record.user_id != input.user_id:
#                 return {"success": False, "message": "Permission denied: reminder does not belong to this user."}
#             if session_record.is_cancelled:
#                 return {"success": False, "message": "Reminder is already cancelled."}
#             if session_record.is_completed:
#                 return {"success": False, "message": "Cannot cancel a reminder that has already fired."}

#             if session_record.task_id:
#                 try:
#                     celery_app.control.revoke(session_record.task_id, terminate=True)
#                 except Exception as exc:
#                     logger.warning(f"Could not revoke task {session_record.task_id}: {exc}")

#             session_record.is_cancelled = True
#             await db.commit()

#             return {"success": True, "message": "Reminder cancelled successfully.", "scheduled_session_id": input.scheduled_session_id}

#     except Exception as e:
#         logger.error(f"[delete_general_reminder] Error for session {input.scheduled_session_id}: {e}")
#         return {"success": False, "message": "An unexpected error occurred."}


class GetOutboundCallLogsInput(BaseModel):
    user_id: int
    start_date: Optional[str] = None  # "YYYY-MM-DD"
    end_date: Optional[str] = None    # "YYYY-MM-DD"


@mcp.tool(
    name="get_outbound_call_logs",
    description=(
        "Retrieve outbound call logs for a user. "
        "Use this tool when you need to check if the user recieved any calls from the system. "
        "Optionally filter by start_date and end_date (YYYY-MM-DD). "
        "Returns a list of {agent_type, datetime} in the user's local timezone."
    )
)
async def get_outbound_call_logs(user_id: int, start_date: Optional[str] = None, end_date: Optional[str] = None) -> list[dict]:
    try:
        async with get_async_session() as db:
            user_result = await db.execute(select(User).where(User.id == user_id))
            user = user_result.scalars().first()
            if not user:
                return []

            tz = get_zoneinfo_safe(user.timezone)

            stmt = (
                select(OutboundCallLog, OrganizationAgents.agent_type)
                .outerjoin(OrganizationAgents, OrganizationAgents.agent_id == OutboundCallLog.agent_id)
                .where(
                    OutboundCallLog.phone_number == user.phone_number,
                    OutboundCallLog.success == True,
                )
            )

            if start_date:
                stmt = stmt.where(OutboundCallLog.created_at >= datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc))
            if end_date:
                end_dt = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
                stmt = stmt.where(OutboundCallLog.created_at <= end_dt)

            stmt = stmt.order_by(OutboundCallLog.created_at.desc())

            result = await db.execute(stmt)
            rows = result.all()

            logs = []
            for log, agent_type in rows:
                local_dt = log.created_at.astimezone(tz) if log.created_at else None
                logs.append({
                    "agent_type": agent_type or log.agent_id,
                    "datetime": local_dt.strftime("%Y-%m-%d %H:%M") if local_dt else None,
                })

            return logs

    except Exception as e:
        logger.error(f"[get_outbound_call_logs] Error for user {user_id}: {e}")
        return []
