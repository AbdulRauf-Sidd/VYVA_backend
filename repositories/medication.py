import logging
from typing import List, Optional
from core.database import get_db
from sqlalchemy.future import select
from schemas.medication import MedicationCreate, MedicationInDB, MedicationUpdate
from models.medication import Medication, MedicationTime
from sqlalchemy import select, and_, or_, exists
from models.user import User
from datetime import date
from sqlalchemy.orm import selectinload, load_only
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.dialects.postgresql import array_agg
from sqlalchemy import func


logger = logging.getLogger(__name__)

class MedicationRepository:
    def __init__(self, db_session: get_db):
        self.db_session = db_session

    async def create(self, medication_data: MedicationCreate) -> MedicationInDB:
        """Create a new medication with times"""
        try:
            # Create medication
            medication_dict = medication_data.model_dump(exclude={"times_of_day"})
            medication = Medication(**medication_dict)
            
            self.db_session.add(medication)
            await self.db_session.flush()
            
            # Create medication times
            for time_data in medication_data.times_of_day:
                medication_time = MedicationTime(
                    medication_id=medication.id,
                    time_of_day=time_data.time_of_day,
                    notes=time_data.notes
                )
                self.db_session.add(medication_time)
            
            logger.info(f"Created medication {medication.name} for user {medication.user_id}")
            await self.db_session.commit()
            await self.db_session.refresh(medication)
            
            return MedicationInDB.model_validate(medication)
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error creating medication: {e}")
            raise

    async def create_bulk(self, medications_data: List[MedicationCreate]) -> List[MedicationInDB]:
        """Create multiple medications with times"""
        try:
            created_medications = []
            
            for medication_data in medications_data:
                medication_dict = medication_data.model_dump(exclude={"times_of_day"})
                medication = Medication(**medication_dict)
                
                self.db_session.add(medication)
                await self.db_session.flush()
                
                # Create medication times
                for time_data in medication_data.times_of_day:
                    medication_time = MedicationTime(
                        medication_id=medication.id,
                        time_of_day=time_data.time_of_day,
                        notes=time_data.notes
                    )
                    self.db_session.add(medication_time)
                
                created_medications.append(medication)
                

            
            await self.db_session.commit()
            
            # Refresh all medications
            for medication in created_medications:
                await self.db_session.refresh(medication)
            
            return [MedicationInDB.model_validate(med) for med in created_medications]
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error creating medications in bulk: {e}")
            raise

    async def get_by_id(self, medication_id: int) -> Optional[MedicationInDB]:
        """Get medication by ID including times"""
        try:
            result = await self.db_session.execute(
                select(Medication).where(Medication.id == medication_id)
            )
            medication = result.scalar_one_or_none()
            
            if medication:
                return MedicationInDB.model_validate(medication)
            return None
            
        except Exception as e:
            logger.error(f"Error fetching medication {medication_id}: {e}")
            raise

    async def get_by_user_id(self, user_id: int) -> List[MedicationInDB]:
        """Get all medications for a user including times"""
        try:
            result = await self.db_session.execute(
                select(Medication).where(Medication.user_id == user_id)
            )
            medications = result.scalars().all()
            
            return [MedicationInDB.model_validate(med) for med in medications]
            
        except Exception as e:
            logger.error(f"Error fetching medications for user {user_id}: {e}")
            raise

    async def update(self, medication_id: int, update_data: MedicationUpdate) -> Optional[MedicationInDB]:
        """Update medication and its times"""
        try:
            result = await self.db_session.execute(
                select(Medication).where(Medication.id == medication_id)
            )
            medication = result.scalar_one_or_none()
            
            if not medication:
                return None
            
            # Update medication fields
            update_dict = update_data.dict(exclude_unset=True, exclude={"times_of_day"})
            for field, value in update_dict.items():
                setattr(medication, field, value)
            
            # Update times if provided
            if update_data.times_of_day is not None:
                # Remove existing times
                await self.db_session.execute(
                    select(MedicationTime).where(MedicationTime.medication_id == medication_id).delete()
                )
                
                # Add new times
                for time_data in update_data.times_of_day:
                    medication_time = MedicationTime(
                        medication_id=medication_id,
                        time_of_day=time_data.time_of_day,
                        notes=time_data.notes
                    )
                    self.db_session.add(medication_time)
            
            await self.db_session.commit()
            await self.db_session.refresh(medication)
            
            return MedicationInDB.model_validate(medication)
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error updating medication {medication_id}: {e}")
            raise

    async def get_active_medications_with_times(self) -> List[dict]:
        """
        Ultra-optimized version focusing only on essential data
        """
        current_date = date.today()
        current_time = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        current_time = current_time.astimezone(ZoneInfo("Europe/Berlin")).time() 
        logging.info(f"curernt time: {current_time}")

        
        query = (
            select(
                User.id.label("user_id"),
                User.first_name,
                User.last_name,
                User.email,
                User.phone_number,
                User.preferred_channel,
                User.wants_caretaker_alerts,
                array_agg(
                    func.json_build_object(
                        "medication_id", Medication.id,
                        "medication_name", Medication.name,
                        "medication_dosage", Medication.dosage,
                        "time_of_day", MedicationTime.time_of_day,
                        "notes", MedicationTime.notes,
                    )
                ).label("medications")
            )
            .join(Medication.user)
            .join(Medication.times_of_day)
            .where(
                User.wants_reminders == True,
                User.takes_medication == True,
                User.is_active == True,
                or_(Medication.start_date.is_(None), Medication.start_date <= current_date),
                or_(Medication.end_date.is_(None), Medication.end_date >= current_date),
                MedicationTime.time_of_day == current_time
            )
            .group_by(User.id, User.first_name, User.last_name, User.email, User.phone_number, User.preferred_channel)
        )

        result = await self.db_session.execute(query)
        rows = result.all()

        response = [{
            "user_id": row.user_id,
            "first_name": row.first_name,
            "last_name": row.last_name,
            "email": row.email,
            "phone_number": row.phone_number,
            "preferred_channel": row.preferred_channel,
            'wants_caretaker_alerts': row.wants_caretaker_alerts,
            "medications": [
                {
                    "medication_id": med["medication_id"],
                    "medication_name": med["medication_name"],
                    "medication_dosage": med["medication_dosage"],
                }
                for med in row.medications or []
            ]
        } for row in rows]


        logger.info(f"Fetched {len(response)} medication time entries for active users")

        return response