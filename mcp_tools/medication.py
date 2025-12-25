from .mcp_instance import mcp
from datetime import time
from pydantic import BaseModel
from models.medication import Medication
from models.medication import MedicationTime
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from core.database import get_async_session

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
            .where(Medication.user_id == user_id)
            .options(selectinload(Medication.times_of_day))
            .order_by(Medication.id)
        )

        result = await db.execute(stmt)
        medications = result.scalars().all()

        return [
            {
                "id": med.id,
                "name": med.name,
                "dosage": med.dosage,
                "purpose": med.purpose,
                # "start_date": med.start_date.isoformat() if med.start_date else None,
                # "end_date": med.end_date.isoformat() if med.end_date else None,
                "times": [
                    t.time_of_day.strftime("%H:%M")
                    for t in med.times_of_day
                    if t.time_of_day
                ],
                # "notes": med.notes,
                # "side_effects": med.side_effects,
            }
            for med in medications
        ]
        
class AddMedication(BaseModel):
    user_id: int
    name: str
    dosage: str
    purpose: str
    times: list[str]
@mcp.tool(
    name="add_medication",
    description=(
        "You will use this tool to add a new medication for a user."
        "You will call this when the user wants to add a new medication."
        "Times should be in 24-hour format."
    )
)

async def add_medication(user_id: int, name: str, dosage: str, purpose: str, times: list[str]) -> AddMedication:

    async with get_async_session() as db:
        new_med = Medication(
            user_id=user_id,
            name=name,
            dosage=dosage,
            purpose=purpose,
        )

        db.add(new_med)
        await db.flush()

        for time_str in times:
            hours, minutes = map(int, time_str.split(":"))
            db.add(
                MedicationTime(
                    medication=new_med,
                    time_of_day=time(hour=hours, minute=minutes)
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
        "Times should be in 24-hour format."
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
        stmt = select(Medication).where(Medication.id == medication_id).options(selectinload(Medication.times_of_day))
        result = await db.execute(stmt)
        medication = result.scalars().first()

        if not medication:
            raise ValueError(f"Medication with ID {medication_id} not found.")

        if name is not None:
            medication.name = name
        if dosage is not None:
            medication.dosage = dosage
        if purpose is not None:
            medication.purpose = purpose

        if times is not None:
            medication.times_of_day.clear()
            await db.flush()

            for time_str in times:
                hours, minutes = map(int, time_str.split(":"))
                db.add(
                    MedicationTime(
                        medication=medication,
                        time_of_day=time(hour=hours, minute=minutes)
                    )
                )

        await db.commit()

        return UpdateUserMedication(
            medication_id=medication.id,
            name=medication.name,
            dosage=medication.dosage,
            purpose=medication.purpose,
            times=[
                t.time_of_day.strftime("%H:%M")
                for t in medication.times_of_day
                if t.time_of_day
            ] if times is not None else None
        )