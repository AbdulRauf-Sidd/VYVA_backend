from .mcp_instance import mcp
from datetime import time
from pydantic import BaseModel
from models.medication import Medication, MedicationTime, MedicationLog, MedicationStatus
from models.user import User
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from core.database import get_async_session
from datetime import datetime, timezone, date, timedelta
from scripts.utils import get_zoneinfo_safe, convert_utc_time_to_local_time, convert_local_time_to_utc_time
from tasks.medication_tasks import notify_caregiver_on_missed_medication_task

class RetrieveMedicationInput(BaseModel):
    user_id: int

@mcp.tool(
    name="retrieve_user_medications",
    description=(
        "You will use this tool to retrieve the list of medications for a user."
    )
)
async def retrieve_user_medications(user_id: int) -> list[dict]:
    async with get_async_session() as db:
        stmt = (
            select(Medication)
            .where(Medication.user_id == user_id, Medication.is_active == True)
            .options(
                selectinload(Medication.times_of_day),
                selectinload(Medication.user)
            )
            .order_by(Medication.id)
        )

        result = await db.execute(stmt)
        medications = result.scalars().all()

        meds = []
        for med in medications:
            # times = []
            # for time in med.times_of_day:
            #     # local_time = convert_utc_time_to_local_time(time.time_of_day, med.user.timezone)
            #     times.append(local_time)

            meds.append(
                {
                    "id": med.id,
                    "name": med.name,
                    "dosage": med.dosage,
                    "purpose": med.purpose,
                    # "start_date": med.start_date.isoformat() if med.start_date else None,
                    # "end_date": med.end_date.isoformat() if med.end_date else None,
                    "times": med.times_of_day
                }
            )
        return meds
        
class AddMedication(BaseModel):
    user_id: int
    name: str
    dosage: str
    purpose: str
    times: list[str]

@mcp.tool(
    name="add_user_medication",
    description=(
        "You will use this tool to add a new medication for a user."
        "You will call this when the user wants to add a new medication."
        "Times should be in 24-hour format. example HH:MM"
        "if the user says 6 in the evening, send 18:00"
    )
)
async def add_user_medication(user_id: int, name: str, dosage: str, purpose: str, times: list[str]) -> AddMedication:

    async with get_async_session() as db:
        stmt = (
            select(User.timezone)
            .where(User.id == user_id)
        )
        result = await db.execute(stmt)
        user_timezone = result.scalars().first()
        tz = get_zoneinfo_safe(user_timezone)
        now_utc = datetime.now(timezone.utc)
        user_now = now_utc.astimezone(tz)
        user_today = user_now.date()

        start_date = user_today
        new_med = Medication(
            user_id=user_id,
            name=name,
            dosage=dosage,
            purpose=purpose,
            start_date=start_date
        )

        db.add(new_med)
        await db.flush()

        for time_str in times:
            hours, minutes = map(int, time_str.split(":"))
            time_obj = time(hour=hours, minute=minutes)
            # utc_time = convert_local_time_to_utc_time(time_obj, user_timezone)
            db.add(
                MedicationTime(
                    medication=new_med,
                    time_of_day=time_obj
                )
            )

        await db.commit()

        return AddMedication(
            id=new_med.id,
            user_id=new_med.user_id,
            name=new_med.name,
            dosage=new_med.dosage,
            purpose=new_med.purpose,
            times=times
        )
        
class UpdateUserMedication(BaseModel):
    medication_id: int
    name: str | None = None
    dosage: str | None = None
    purpose: str | None = None
    times: list[str] | None = None
    
@mcp.tool(
    name="update_user_medication",
    description=(
        "You will use this tool to update an existing medication for a user."
        "You will call this when the user wants to update their medication details."
        "Times should be in 24-hour format. Format: HH:MM"
        "Example: if the user says 6 in the evening, send 18:00"
    )
)
async def update_user_medication(
    medication_id: int,
    name: str | None = None,
    dosage: str | None = None,
    purpose: str | None = None,
    times: list[str] | None = None
) -> UpdateUserMedication:

    async with get_async_session() as db:

        stmt = (
            select(Medication)
            .where(Medication.id == medication_id)
            .options(selectinload(Medication.times_of_day))
            .options(selectinload(Medication.user))
        )

        result = await db.execute(stmt)
        old_med = result.scalars().first()

        if not old_med:
            raise ValueError(f"Medication with ID {medication_id} not found.")

        # 🔹 1️⃣ Close old medication (end today)
        tz = get_zoneinfo_safe(old_med.user.timezone)
        now_utc = datetime.now(timezone.utc)
        user_now = now_utc.astimezone(tz)
        user_today = user_now.date()
        old_med.end_date = user_today
        old_med.is_active = False
        old_med.disabled_at = now_utc

        await db.flush()

        # 🔹 2️⃣ Create new medication starting today
        today = user_today

        new_med = Medication(
            user_id=old_med.user_id,
            name=name if name is not None else old_med.name,
            dosage=dosage if dosage is not None else old_med.dosage,
            purpose=purpose if purpose is not None else old_med.purpose,
            start_date=today,
            end_date=None,
            notes=old_med.notes,
            side_effects=old_med.side_effects,
            is_active=True
        )

        db.add(new_med)
        await db.flush()
        if times is not None:
            # convert=True
            time_strings = times
        else:
            # convert=False
            time_strings = [
                t.time_of_day.strftime("%H:%M")
                for t in old_med.times_of_day
                if t.time_of_day
            ]

        for time_str in time_strings:
            hours, minutes = map(int, time_str.split(":"))
            time_obj = time(hour=hours, minute=minutes)
            # if convert:
            #     time_obj = convert_local_time_to_utc_time(time_obj, old_med.user.timezone)

            db.add(
                MedicationTime(
                    medication_id=new_med.id,
                    time_of_day=time_obj
                )
            )

        await db.commit()

        return UpdateUserMedication(
            medication_id=new_med.id,
            name=new_med.name,
            dosage=new_med.dosage,
            purpose=new_med.purpose,
            times=time_strings
        )
        
class DeleteUserMedication(BaseModel):
    medication_id: int

@mcp.tool(
    name="end_user_medication",
    description=(
        "You will use this tool to end a medication for a user."
        "You will call this when the user wants to remove a medication from their list."
    )
)
async def end_user_medication(medication_id: int) -> DeleteUserMedication:
    async with get_async_session() as db:
        stmt = (
            select(Medication)
            .where(Medication.id == medication_id)
            .options(selectinload(Medication.user))
        )
        result = await db.execute(stmt)
        medication = result.scalars().first()

        if not medication:
            raise ValueError(f"Medication with ID {medication_id} not found.")
        
        tz = get_zoneinfo_safe(medication.user.timezone)
        now_utc = datetime.now(timezone.utc)
        user_now = now_utc.astimezone(tz)
        user_today = user_now.date()
        
        medication.end_date = user_today
        medication.is_active = False
        medication.disabled_at = now_utc

        await db.commit()

        return DeleteUserMedication(medication_id=medication_id)
    

class UpdateReminderChannel(BaseModel):
    user_id: int
    channel: str

@mcp.tool(
    name="update_reminder_channel",
    description=(
        "You will use this tool to update the reminder channel for a medication."
        "You will call this when the user wants to change how they receive reminders."
        "options are 1. app. 2. phone. 3. whatsapp"
    )
)
async def update_reminder_channel(channel_input: UpdateReminderChannel) -> bool:
    async with get_async_session() as db:
        stmt = select(User).where(User.id == channel_input.user_id)
        result = await db.execute(stmt)
        user = result.scalars().first()

        if not user:
            raise ValueError(f"User with ID {channel_input.user_id} not found.")

        # Update the user's reminder channel
        user.preferred_reminder_channel = channel_input.channel.lower()
        await db.commit()

        return True
    

class MedicationLogInput(BaseModel):
    user_id: int
    medication_logs: list[dict]

@mcp.tool(
    name="medication_log",
    description=(
        "Use this tool to update the user's medication log. "
        "Call this tool only if the user wants to log their medication intake. "
        "You will ask which medications (and times) they want to update the log, submit the results using this tool.\n\n"
        "Example input format:\n"
        "{\n"
        "  user_id: 4,\n"
        "  medication_logs: [\n"
        "    {\n"
        "      medication_id: 3,\n"
        "      time_id: 5,\n"
        "      taken: true\n"
        "    }\n"
        "  ]\n"
        "}" \
    )
)

async def update_medication_log(input: MedicationLogInput) -> dict:
    async with get_async_session() as db:
        if not input.user_id:
            raise ValueError(f"User with ID {input.user_id} not found.")
        
        if not input.medication_logs:
            raise ValueError(f"Med Logs not found.")
        
        # Fetch user timezone
        stmt = select(User.timezone).where(User.id == input.user_id)
        result = await db.execute(stmt)
        user_timezone = result.scalars().first()
        tz = get_zoneinfo_safe(user_timezone)
        now_utc = datetime.now(timezone.utc)
        user_now = now_utc.astimezone(tz)
        
        for med in input.medication_logs:
            med_taken = med['taken']

            # Find the latest log for this medication and time
            stmt = select(MedicationLog).where(
                MedicationLog.medication_id == med['medication_id'],
                MedicationLog.medication_time_id == med['time_id'],
                MedicationLog.user_id == input.user_id
            ).order_by(MedicationLog.created_at.desc()).limit(1)
            result = await db.execute(stmt)
            log = result.scalars().first()

            if log:
                log.status = MedicationStatus.taken.value if med_taken else MedicationStatus.missed.value
                log.taken_at = now_utc if med_taken else None
                log.taken_at_local = user_now if med_taken else None
            else:
                # Fallback: create new log if none exists
                log = MedicationLog(
                    medication_id=med['medication_id'],
                    medication_time_id=med['time_id'],
                    user_id=input.user_id,
                    taken_at=now_utc if med_taken else None,
                    taken_at_local=user_now if med_taken else None,
                    status=MedicationStatus.taken.value if med_taken else MedicationStatus.missed.value
                )
                db.add(log)

        await db.commit()

        if input.reminder:
            message = "meds scheduled for reminder. "
            return {
                "success": True,
                "message": message
            }
        else:
            return {
                "success": True,
                "message": "Congratulate User on taking medications."
            }
    

