from main import mcp
from pydantic import BaseModel
# from core.database import get_db_session
from models.medication import Medication
from sqlalchemy.orm import selectinload
from sqlalchemy import select

# class RetrieveMedicationInput(BaseModel):
#     user_id: int

# @mcp.tool(
#     name="Retrieve Medications",
#     description=(
#         "You will use this tool to retrieve the list of medications for a user."
#     )
# )
# async def get_user_medications(
#     db: AsyncSession,
#     user_id: int
# ) -> list[dict]:
#     stmt = (
#         select(Medication)
#         .where(Medication.user_id == user_id)
#         .options(selectinload(Medication.times_of_day))
#         .order_by(Medication.id)
#     )

#     result = await db.execute(stmt)
#     medications = result.scalars().all()

#     return [
#         {
#             "id": med.id,
#             "name": med.name,
#             "dosage": med.dosage,
#             "purpose": med.purpose,
#             "start_date": med.start_date.isoformat() if med.start_date else None,
#             "end_date": med.end_date.isoformat() if med.end_date else None,
#             "times": [
#                 t.time_of_day.strftime("%H:%M")
#                 for t in med.times_of_day
#                 if t.time_of_day
#             ],
#             "notes": med.notes,
#             "side_effects": med.side_effects,
#         }
#         for med in medications
#     ]