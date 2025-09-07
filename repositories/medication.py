from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional
from datetime import datetime, time
import logging
from core.database import get_db
from models.medication import Medication, MedicationTime
from schemas.medication import MedicationCreate, MedicationRead

logger = logging.getLogger(__name__)

class MedicationRepository:
    def __init__(self, db_session: Session):
        self.db_session = db_session

    async def create_medication_with_times(
        self, medication_data: MedicationCreate
    ) -> MedicationRead:
        """Create a new medication with times of day"""
        try:
            # Validate required fields
            if not medication_data.name.strip():
                raise ValueError("Medication name cannot be empty")
            if not medication_data.dosage.strip():
                raise ValueError("Dosage cannot be empty")
            if not medication_data.frequency.strip():
                raise ValueError("Frequency cannot be empty")
            
            # Validate dosage format
            if not any(char.isdigit() for char in medication_data.dosage):
                raise ValueError("Dosage should contain numeric values (e.g., '10mg', '1 tablet')")
            
            # Validate date consistency
            if (medication_data.start_date and medication_data.end_date and 
                medication_data.start_date > medication_data.end_date):
                raise ValueError("Start date cannot be after end date")
            
            # Validate time data if provided
            if medication_data.times_of_day:
                for time_data in medication_data.times_of_day:
                    if time_data.time_of_day and not isinstance(time_data.time_of_day, time):
                        raise ValueError("Time of day must be a valid time object")
                    if time_data.notes and len(time_data.notes) > 150:
                        raise ValueError("Time notes cannot exceed 150 characters")

            # Create base medication
            base_medication = Medication(
                user_id=medication_data.user_id,
                name=medication_data.name.strip(),
                dosage=medication_data.dosage.strip(),
                frequency=medication_data.frequency.strip(),
                start_date=medication_data.start_date,
                end_date=medication_data.end_date,
                purpose=medication_data.purpose,
                side_effects=medication_data.side_effects,
                notes=medication_data.notes
            )
            self.db_session.add(base_medication)
            await self.db_session.flush()

            # Create medication times
            if medication_data.times_of_day:
                for time_data in medication_data.times_of_day:
                    new_time = MedicationTime(
                        medication_id=base_medication.id,
                        time_of_day=time_data.time_of_day,
                        notes=time_data.notes
                    )
                    self.db_session.add(new_time)

            await self.db_session.commit()
            await self.db_session.refresh(base_medication)

            # Return the complete medication with times
            return await self.get_medication_by_id(base_medication.id)

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error creating medication: {e}")
            raise

    async def get_medication_by_id(self, medication_id: int) -> Optional[MedicationRead]:
        """Get medication by ID with times of day"""
        try:
            if medication_id <= 0:
                raise ValueError("Medication ID must be a positive integer")

            medication = await self.db_session.query(Medication)\
                .filter(Medication.id == medication_id)\
                .options(joinedload(Medication.times_of_day))\
                .first()
            
            if not medication:
                return None
            
            return medication

        except SQLAlchemyError as e:
            logger.error(f"Error getting medication {medication_id}: {e}")
            raise

    async def get_medications_by_user_id(self, user_id: int) -> List[MedicationRead]:
        """Get all medications for a user with their times of day"""
        try:
            if user_id <= 0:
                raise ValueError("User ID must be a positive integer")

            medications = await self.db_session.query(Medication)\
                .filter(Medication.user_id == user_id)\
                .options(joinedload(Medication.times_of_day))\
                .all()
            
            return medications

        except SQLAlchemyError as e:
            logger.error(f"Error getting medications for user {user_id}: {e}")
            raise

    async def update_medication(
        self, medication_id: int, update_data: dict
    ) -> Optional[MedicationRead]:
        """Update a medication"""
        try:
            if medication_id <= 0:
                raise ValueError("Medication ID must be a positive integer")

            # Get existing medication
            medication = await self.db_session.query(Medication)\
                .filter(Medication.id == medication_id)\
                .first()
            
            if not medication:
                return None

            # Validate update data
            if 'name' in update_data and not update_data['name'].strip():
                raise ValueError("Medication name cannot be empty")
            if 'dosage' in update_data and not update_data['dosage'].strip():
                raise ValueError("Dosage cannot be empty")
            if 'frequency' in update_data and not update_data['frequency'].strip():
                raise ValueError("Frequency cannot be empty")
            
            if 'dosage' in update_data and not any(char.isdigit() for char in update_data['dosage']):
                raise ValueError("Dosage should contain numeric values")

            # Update fields
            for field, value in update_data.items():
                if hasattr(medication, field):
                    setattr(medication, field, value)

            await self.db_session.commit()
            await self.db_session.refresh(medication)

            # Return updated medication with times
            return await self.get_medication_by_id(medication_id)

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error updating medication {medication_id}: {e}")
            raise

    async def create_user_medications_bulk(
        self, user_id: int, medications_data: List[MedicationCreate]
    ) -> List[MedicationRead]:
        """Create multiple medications with times for a user in bulk"""
        try:
            if user_id <= 0:
                raise ValueError("User ID must be a positive integer")

            created_medications = []
            
            for medication_data in medications_data:
                # Set the user_id for each medication
                medication_data.user_id = user_id
                medication = await self.create_medication_with_times(medication_data)
                created_medications.append(medication)

            return created_medications

        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Error creating bulk medications for user {user_id}: {e}")
            raise