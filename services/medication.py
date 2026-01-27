import logging
from typing import Dict, List, Optional
from datetime import time, date
from schemas.responses import MedicationEntry
from sqlalchemy.orm import Session
from models.medication import Medication, MedicationTime
from schemas.medication import MedicationCreate, MedicationInDB, MedicationUpdate, BulkMedicationRequest, MedicationTimeCreate
from repositories.medication import MedicationRepository
from datetime import datetime, timedelta
logger = logging.getLogger(__name__)

class MedicationService:
    def __init__(self, medication_repository: MedicationRepository):
        self.medication_repository = medication_repository

    async def create_medication(self, medication_data: MedicationCreate) -> MedicationInDB:
        """Create a new medication with validation"""
        try:
            # Validate medication data
            self._validate_medication_data(medication_data)
            
            # Create medication
            return await self.medication_repository.create(medication_data)
            
        except ValueError as e:
            logger.warning(f"Validation error creating medication: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating medication: {e}")
            raise

    async def create_medications_bulk(self, medications_data: List[MedicationCreate]) -> bool:
        """Create multiple medications with validation"""
        try:
            if not medications_data:
                raise ValueError("No medications provided")
            
            # Validate each medication
            for medication_data in medications_data:
                self._validate_medication_data(medication_data)
            
            # Create medications
            return await self.medication_repository.create_bulk(medications_data)
            
        except ValueError as e:
            logger.warning(f"Validation error creating medications in bulk: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error creating medications in bulk: {e}")
            raise

    async def get_medication(self, medication_id: int) -> Optional[MedicationInDB]:
        """Get medication by ID"""
        try:
            if not medication_id or medication_id <= 0:
                raise ValueError("Invalid medication ID")
            
            return await self.medication_repository.get_by_id(medication_id)
            
        except ValueError as e:
            logger.warning(f"Validation error getting medication: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting medication {medication_id}: {e}")
            raise

    async def get_user_medications(self, user_id: int) -> List[MedicationInDB]:
        """Get all medications for a user"""
        try:
            if not user_id or user_id <= 0:
                raise ValueError("Invalid user ID")
            
            return await self.medication_repository.get_by_user_id(user_id)
            
        except ValueError as e:
            logger.warning(f"Validation error getting user medications: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error getting medications for user {user_id}: {e}")
            raise

    async def update_medication(self, medication_id: int, update_data: MedicationUpdate) -> Optional[MedicationInDB]:
        """Update medication with validation"""
        try:
            if not medication_id or medication_id <= 0:
                raise ValueError("Invalid medication ID")
            
            # Validate update data if provided
            if update_data.name is not None and not update_data.name.strip():
                raise ValueError("Medication name cannot be empty")
            
            if update_data.dosage is not None and not update_data.dosage.strip():
                raise ValueError("Dosage cannot be empty")
            
            if update_data.times_of_day is not None:
                self._validate_times_of_day(update_data.times_of_day)
            
            if (update_data.start_date and update_data.end_date and 
                update_data.start_date > update_data.end_date):
                raise ValueError("Start date cannot be after end date")
            
            # Update medication
            return await self.medication_repository.update(medication_id, update_data)
            
        except ValueError as e:
            logger.warning(f"Validation error updating medication: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error updating medication {medication_id}: {e}")
            raise

    async def process_bulk_medication_request(self, request_data: BulkMedicationRequest) -> bool:
        """Process bulk medication request from API input"""
        try:
            # Convert input format to MedicationCreate objects
            medications_to_create = []
            
            for med_input in request_data.medication_details:
                # Convert string times to time objects
                time_objects = []
                for time_str in med_input.times:
                    time_obj = self._parse_time_string(time_str)
                    time_objects.append(MedicationTimeCreate(time_of_day=time_obj))
                
                start_date_obj = datetime.strptime(str(med_input.start_date), "%Y-%m-%d").date() if med_input.start_date else date.today()
                # end_date_obj = start_date_obj + timedelta(days=3) if start_date_obj else None

                # Create MedicationCreate object
                medication_create = MedicationCreate(
                    user_id=request_data.user_id,
                    name=med_input.name,
                    dosage=med_input.dosage,
                    start_date=med_input.start_date,
                    end_date=med_input.end_date,
                    purpose=med_input.purpose,
                    times_of_day=time_objects
                )
                
                medications_to_create.append(medication_create)
            
            # Create medications
            return await self.create_medications_bulk(medications_to_create)
            
        except Exception as e:
            logger.error(f"Error processing bulk medication request: {e}")
            raise

    def _validate_medication_data(self, medication_data: MedicationCreate) -> None:
        """Validate medication data"""
        if not medication_data.name.strip():
            raise ValueError("Medication name cannot be empty")
        
        if not medication_data.dosage.strip():
            raise ValueError("Dosage cannot be empty")
        
        if not medication_data.times_of_day:
            raise ValueError("At least one medication time is required")
        
        self._validate_times_of_day(medication_data.times_of_day)
        
        if (medication_data.start_date and medication_data.end_date and 
            medication_data.start_date > medication_data.end_date):
            raise ValueError("Start date cannot be after end date")

    def _validate_times_of_day(self, times_of_day: List) -> None:
        """Validate medication times"""
        if not times_of_day:
            raise ValueError("At least one medication time is required")
        
        for time_data in times_of_day:
            if not time_data.time_of_day:
                raise ValueError("Time of day is required")
            

    def _parse_time_string(self, time_str: str) -> time:
        """Parse time string (e.g., '09:00') to time object"""
        try:
            hours, minutes = map(int, time_str.split(':'))
            return time(hour=hours, minute=minutes)
        except (ValueError, AttributeError):
            raise ValueError(f"Invalid time format: {time_str}. Expected format: 'HH:MM'")
        
    async def get_weekly_medication_schedule(self, user_id: int) -> Dict[str, List[MedicationEntry]]:
        try:
            medications = await self.get_user_medications(user_id)
            schedule = { (date.today() + timedelta(days=i)).strftime("%A"): [] for i in range(7) }
            
            for med in medications:
                for med_time in med.times_of_day:
                    for i in range(7):
                        day = date.today() + timedelta(days=i)
                        if (med.start_date <= day and 
                            (med.end_date is None or med.end_date >= day)):
                            entry = MedicationEntry(
                                medication_name=med.name,
                                time=med_time.time_of_day.strftime("%H:%M"),
                                log=None  
                            )
                            schedule[day.strftime("%A")].append(entry)
            
            return schedule
            
        except Exception as e:
            logger.error(f"Error getting weekly medication schedule for user {user_id}: {e}")
            raise