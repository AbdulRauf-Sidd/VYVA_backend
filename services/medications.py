from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from typing import List, Optional, Dict, Any
import logging
from datetime import datetime, time
from repositories.medication import MedicationRepository
from schemas.medication import MedicationCreate, MedicationRead, MedicationUpdate
from models.medication import Medication

logger = logging.getLogger(__name__)

class MedicationService:
    """Service for medication business logic."""
    
    def __init__(self, db: Session):
        self.db = db
        self.medication_repo = MedicationRepository(db)
    
    async def create_medications_bulk(
        self, 
        user_id: int, 
        medications_data: List[MedicationCreate]
    ) -> List[MedicationRead]:
        """
        Create multiple medications for a user in bulk with validation.
        
        Args:
            user_id: ID of the user to create medications for
            medications_data: List of medication creation data
            
        Returns:
            List of created medications
            
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails
        """
        try:
            # Validate user_id
            if user_id <= 0:
                raise ValueError("User ID must be a positive integer")
            
            # Validate medications data is not empty
            if not medications_data:
                raise ValueError("Medications data cannot be empty")
            
            # Validate each medication
            for i, medication_data in enumerate(medications_data):
                await self._validate_medication_data(medication_data, user_id, index=i)
            
            # Create medications in bulk
            medications = await self.medication_repo.create_user_medications_bulk(
                user_id, medications_data
            )
            
            logger.info(f"Successfully created {len(medications)} medications for user {user_id}")
            return medications
            
        except ValueError as e:
            logger.warning(f"Validation error in bulk medication creation for user {user_id}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error in bulk medication creation for user {user_id}: {e}")
            raise Exception("Failed to create medications due to database error")
        except Exception as e:
            logger.error(f"Unexpected error in bulk medication creation for user {user_id}: {e}")
            raise
    
    async def get_user_medications(self, user_id: int) -> List[MedicationRead]:
        """
        Get all medications for a specific user.
        
        Args:
            user_id: ID of the user to retrieve medications for
            
        Returns:
            List of user's medications
            
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails
        """
        try:
            # Validate user_id
            if user_id <= 0:
                raise ValueError("User ID must be a positive integer")
            
            # Get medications from repository
            medications = await self.medication_repo.get_medications_by_user_id(user_id)
            
            logger.info(f"Retrieved {len(medications)} medications for user {user_id}")
            return medications
            
        except ValueError as e:
            logger.warning(f"Validation error getting medications for user {user_id}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error getting medications for user {user_id}: {e}")
            raise Exception("Failed to retrieve medications due to database error")
        except Exception as e:
            logger.error(f"Unexpected error getting medications for user {user_id}: {e}")
            raise
    
    async def get_medication(self, medication_id: int, user_id: int) -> Optional[MedicationRead]:
        """
        Get a specific medication with ownership validation.
        
        Args:
            medication_id: ID of the medication to retrieve
            user_id: ID of the user who should own the medication
            
        Returns:
            Medication if found and owned by user, None otherwise
            
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails
        """
        try:
            # Validate IDs
            if medication_id <= 0:
                raise ValueError("Medication ID must be a positive integer")
            if user_id <= 0:
                raise ValueError("User ID must be a positive integer")
            
            # Get medication from repository
            medication = await self.medication_repo.get_medication_by_id(medication_id)
            
            # Check if medication exists and belongs to user
            if not medication:
                logger.info(f"Medication {medication_id} not found")
                return None
            
            if medication.user_id != user_id:
                logger.warning(f"User {user_id} attempted to access medication {medication_id} owned by user {medication.user_id}")
                return None
            
            logger.info(f"Retrieved medication {medication_id} for user {user_id}")
            return medication
            
        except ValueError as e:
            logger.warning(f"Validation error getting medication {medication_id}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error getting medication {medication_id}: {e}")
            raise Exception("Failed to retrieve medication due to database error")
        except Exception as e:
            logger.error(f"Unexpected error getting medication {medication_id}: {e}")
            raise
    
    async def update_medication(
        self, 
        medication_id: int, 
        user_id: int, 
        update_data: Dict[str, Any]
    ) -> Optional[MedicationRead]:
        """
        Update a specific medication with ownership validation.
        
        Args:
            medication_id: ID of the medication to update
            user_id: ID of the user who should own the medication
            update_data: Dictionary of fields to update
            
        Returns:
            Updated medication if successful, None otherwise
            
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails
        """
        try:
            # Validate IDs
            if medication_id <= 0:
                raise ValueError("Medication ID must be a positive integer")
            if user_id <= 0:
                raise ValueError("User ID must be a positive integer")
            
            # Validate update data is not empty
            if not update_data:
                raise ValueError("Update data cannot be empty")
            
            # Validate specific fields if they are being updated
            await self._validate_update_data(update_data)
            
            # First verify the medication exists and belongs to the user
            existing_medication = await self.medication_repo.get_medication_by_id(medication_id)
            if not existing_medication or existing_medication.user_id != user_id:
                logger.warning(f"Update failed: Medication {medication_id} not found or not owned by user {user_id}")
                return None
            
            # Update the medication
            updated_medication = await self.medication_repo.update_medication(
                medication_id, update_data
            )
            
            if not updated_medication:
                logger.warning(f"Update failed: Medication {medication_id} not found after update attempt")
                return None
            
            logger.info(f"Successfully updated medication {medication_id} for user {user_id}")
            return updated_medication
            
        except ValueError as e:
            logger.warning(f"Validation error updating medication {medication_id}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error updating medication {medication_id}: {e}")
            raise Exception("Failed to update medication due to database error")
        except Exception as e:
            logger.error(f"Unexpected error updating medication {medication_id}: {e}")
            raise
    
    async def delete_medication(self, medication_id: int, user_id: int) -> bool:
        """
        Delete a specific medication with ownership validation.
        
        Args:
            medication_id: ID of the medication to delete
            user_id: ID of the user who should own the medication
            
        Returns:
            True if deletion was successful, False otherwise
            
        Raises:
            ValueError: If validation fails
            Exception: If database operation fails
        """
        try:
            # Validate IDs
            if medication_id <= 0:
                raise ValueError("Medication ID must be a positive integer")
            if user_id <= 0:
                raise ValueError("User ID must be a positive integer")
            
            # First verify the medication exists and belongs to the user
            existing_medication = await self.medication_repo.get_medication_by_id(medication_id)
            if not existing_medication or existing_medication.user_id != user_id:
                logger.warning(f"Delete failed: Medication {medication_id} not found or not owned by user {user_id}")
                return False
            
            # Delete the medication
            success = await self.medication_repo.delete_medication(medication_id)
            
            if success:
                logger.info(f"Successfully deleted medication {medication_id} for user {user_id}")
            else:
                logger.warning(f"Delete failed: Medication {medication_id} not found during deletion")
            
            return success
            
        except ValueError as e:
            logger.warning(f"Validation error deleting medication {medication_id}: {e}")
            raise
        except SQLAlchemyError as e:
            logger.error(f"Database error deleting medication {medication_id}: {e}")
            raise Exception("Failed to delete medication due to database error")
        except Exception as e:
            logger.error(f"Unexpected error deleting medication {medication_id}: {e}")
            raise
    
    async def _validate_medication_data(self, medication_data: MedicationCreate, user_id: int, index: int = None) -> None:
        """Validate medication data before creation."""
        prefix = f"Medication [{index}]: " if index is not None else ""
        
        # Validate required fields
        if not medication_data.name or not medication_data.name.strip():
            raise ValueError(f"{prefix}Medication name is required")
        
        if not medication_data.dosage or not medication_data.dosage.strip():
            raise ValueError(f"{prefix}Dosage is required")
        
        if not medication_data.frequency or not medication_data.frequency.strip():
            raise ValueError(f"{prefix}Frequency is required")
        
        # Validate dosage format
        if not any(char.isdigit() for char in medication_data.dosage):
            raise ValueError(f"{prefix}Dosage should contain numeric values (e.g., '10mg', '1 tablet')")
        
        # Validate date consistency
        if (medication_data.start_date and medication_data.end_date and 
            medication_data.start_date > medication_data.end_date):
            raise ValueError(f"{prefix}Start date cannot be after end date")
        
        # Validate user_id matches
        if medication_data.user_id != user_id:
            raise ValueError(f"{prefix}User ID in medication data does not match target user")
    
    async def _validate_update_data(self, update_data: Dict[str, Any]) -> None:
        """Validate update data before applying changes."""
        
        if 'name' in update_data and (not update_data['name'] or not update_data['name'].strip()):
            raise ValueError("Medication name cannot be empty")
        
        if 'dosage' in update_data and (not update_data['dosage'] or not update_data['dosage'].strip()):
            raise ValueError("Dosage cannot be empty")
        
        if 'frequency' in update_data and (not update_data['frequency'] or not update_data['frequency'].strip()):
            raise ValueError("Frequency cannot be empty")
        
        if 'dosage' in update_data and not any(char.isdigit() for char in update_data['dosage']):
            raise ValueError("Dosage should contain numeric values")
        
        # Validate date consistency if both dates are being updated
        if ('start_date' in update_data and 'end_date' in update_data and 
            update_data['start_date'] and update_data['end_date'] and 
            update_data['start_date'] > update_data['end_date']):
            raise ValueError("Start date cannot be after end date")