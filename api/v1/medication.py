from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
import logging
from datetime import datetime
from core.database import get_db
from services.medication import MedicationService
from schemas.medication import (
    MedicationCreate, 
    MedicationRead, 
    MedicationUpdate,
    # HTTPErrorResponse
)


from repositories.user import UserRepository

router = APIRouter()
logger = logging.getLogger(__name__)

# Common error responses
# ERROR_RESPONSES = {
#     400: {"model": HTTPErrorResponse, "description": "Bad Request - Validation error"},
#     401: {"model": HTTPErrorResponse, "description": "Unauthorized - Invalid credentials"},
#     403: {"model": HTTPErrorResponse, "description": "Forbidden - Access denied"},
#     404: {"model": HTTPErrorResponse, "description": "Not Found - Resource not found"},
#     500: {"model": HTTPErrorResponse, "description": "Internal Server Error"}
# }



@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Create multiple medications for a user",
    description="Create multiple medications for a user with their times of day in a single operation."
)
async def create_medications_bulk(
    medications_data: List[MedicationCreate],
    background_tasks: BackgroundTasks,
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Create multiple medications for a user in bulk.
    
    - **user_id**: ID of the user to create medications for
    - **medications_data**: List of medication creation data
    """
    try:

        # FIRST CREATE USER RECORD WITH NO DETAILS, THEN PASS THIS USER ID TO MEDICATION CREATION 
        medication_service = MedicationService(db)
        medications = await medication_service.create_medications_bulk(user_id, medications_data)       
        return medications #REPLACE THIS WITH USER_ID. JUST USER_ID SHOULD BE RETURNED 
        
    except ValueError as e:
        logger.warning(f"Validation error creating bulk medications for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating bulk medications for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while creating medications"
        )

@router.get(
    "",
    response_model=List[MedicationRead],
    summary="Get user medications",
    description="Retrieve all medications for a specific user including their times of day."
)
async def get_user_medications(
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get all medications for a specific user.
    
    - **user_id**: ID of the user to retrieve medications for
    """
    try:
        medication_service = MedicationService(db)
        medications = await medication_service.get_user_medications(user_id)
        
        if not medications:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No medications found for this user"
            )
        
        return medications
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting medications for user {user_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving medications"
        )

@router.get(
    "/{medication_id}",
    response_model=MedicationRead,
    summary="Get specific medication",
    description="Retrieve a specific medication by ID with ownership validation."
)
async def get_medication(
    medication_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """
    Get a specific medication by ID.
    
    - **user_id**: ID of the user who owns the medication
    - **medication_id**: ID of the medication to retrieve
    """
    try:
        # Initialize service
        medication_service = MedicationService(db)
        medication = await medication_service.get_medication(medication_id, user_id)
        
        if not medication:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medication not found or you don't have access to it"
            )
        
        return medication
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error getting medication {medication_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while retrieving the medication"
        )

@router.put(
    "/{medication_id}",
    response_model=MedicationRead,
    summary="Update medication",
    description="Update a specific medication with validation and ownership check."
)
async def update_medication(
    user_id: int,
    medication_id: int,
    update_data: MedicationUpdate,
    db: Session = Depends(get_db)
):
    """
    Update a specific medication.
    
    - **user_id**: ID of the user who owns the medication
    - **medication_id**: ID of the medication to update
    - **update_data**: Fields to update
    """
    try:
        # Initialize service
        medication_service = MedicationService(db)
        # Convert Pydantic model to dict for the service
        update_dict = update_data.dict(exclude_unset=True)
        # Update medication using service (includes ownership validation)
        medication = await medication_service.update_medication(medication_id, user_id, update_dict)
        
        if not medication:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medication not found or you don't have permission to update it"
            )
        
        return medication
        
    except ValueError as e:
        logger.warning(f"Validation error updating medication {medication_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error updating medication {medication_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while updating the medication"
        )

@router.delete(
    "/{medication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete medication",
    description="Delete a specific medication with ownership validation."
)
async def delete_medication(
    medication_id: int,
    user_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a specific medication.
    
    - **user_id**: ID of the user who owns the medication
    - **medication_id**: ID of the medication to delete
    """
    try:
        # Initialize service
        medication_service = MedicationService(db)
        
        # Delete medication using service (includes ownership validation)
        success = await medication_service.delete_medication(medication_id, user_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medication not found or you don't have permission to delete it"
            )
        
        # No content response for successful deletion
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error deleting medication {medication_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while deleting the medication"
        )












# Background task functions
async def log_bulk_creation(user_id: int, medication_count: int, medication_ids: List[int]):
    """Background task to log bulk medication creation."""
    try:
        logger.info(
            f"User {user_id} successfully created {medication_count} medications. "
            f"Medication IDs: {medication_ids}"
        )
        # Add any additional logging, analytics, or notifications here
    except Exception as e:
        logger.error(f"Error in background task for bulk medication creation: {e}")

async def send_medication_notification(user_id: int, medication_id: int, action: str):
    """Background task to send notifications about medication changes."""
    try:
        logger.info(f"Sending {action} notification for medication {medication_id} to user {user_id}")
        # Implement notification logic here (email, push, etc.)
    except Exception as e:
        logger.error(f"Error sending medication notification: {e}")