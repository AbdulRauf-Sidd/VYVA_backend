from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import logging
import time
from core.database import get_db
from services.medication import MedicationService
from repositories.user import UserRepository
from repositories.medication import MedicationRepository
from schemas.medication import (
    BulkMedicationRequest,
    MedicationCreate,
    MedicationUpdate,
    MedicationInDB
)

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.post(
    "",
    response_model=List[MedicationInDB],
    status_code=status.HTTP_201_CREATED,
    summary="Create multiple medications"
)
async def bulk_create_medications(
    request: BulkMedicationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create multiple medications with their times in a single request.
    """
    start_time = time.time()
    request_id = f"bulk_create_{int(start_time * 1000)}"
    
    logger.info(
        f"Request {request_id}: Starting bulk medication creation for user {request.user_id} "
        f"with {len(request.medication_details)} medications"
    )
    
    try:
        first_name = request.first_name or "User"
        last_name = request.last_name or ""
        user_repo = UserRepository(db)
        user_params = {
            'first_name': first_name,
            'last_name': last_name,
            'channel': request.channel,
            'email': request.email,
            'phone': request.phone,
            # 'want_caretaker_alerts': request.want_caretaker_alerts if request.want_caretaker_alerts is not None else True,
            # 'wants_reminders': True,
            # 'takes_medication': True,
            # 'missed_dose_alerts': True,
            # 'caretaker_preferred_channel': request.caretaker_channel,
            # 'caretaker_email': request.caretaker_email,
            # 'caretaker_phone_number': request.caretaker_phone
        }
        user = await user_repo.create_user(user_params)
        logger.debug(f"Request {request_id}: Created user {user.id} for medication assignment")
        request['user_id'] = user.id
        logger.debug(f"Request {request_id}: request body {request}")
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        logger.debug(
            f"Request {request_id}: Processing medications: {[med.name for med in request.medication_details]}"
        )
        
        result = await medication_service.process_bulk_medication_request(request)
        
        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Successfully created {len(result)} medications "
            f"for user {request.user_id} in {duration:.2f}s"
        )
        
        return result
        
    except ValueError as e:
        logger.warning(
            f"Request {request_id}: Validation failed for user {request.user_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Request {request_id}: Unexpected error creating medications for user {request.user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create medications"
        )

@router.get(
    "/user/{user_id}",
    response_model=List[MedicationInDB],
    summary="Get all medications for a user"
)
async def get_user_medications(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve all medications for a specific user, including medication times.
    """
    start_time = time.time()
    request_id = f"get_user_{user_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Fetching medications for user {user_id}")
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        result = await medication_service.get_user_medications(user_id)
        
        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Found {len(result)} medications for user {user_id} "
            f"in {duration:.2f}s"
        )
        
        if not result:
            logger.debug(f"Request {request_id}: No medications found for user {user_id}")
        
        return result
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Invalid user ID {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to fetch medications for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch medications"
        )

@router.get(
    "/{medication_id}",
    response_model=MedicationInDB,
    summary="Get a specific medication"
)
async def get_medication(
    medication_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Retrieve a specific medication by ID, including its times.
    """
    start_time = time.time()
    request_id = f"get_med_{medication_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Fetching medication {medication_id}")
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        result = await medication_service.get_medication(medication_id)
        
        duration = time.time() - start_time
        if result:
            logger.info(
                f"Request {request_id}: Found medication '{result.name}' (ID: {medication_id}) "
                f"in {duration:.2f}s"
            )
        else:
            logger.warning(f"Request {request_id}: Medication {medication_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medication not found"
            )
            
        return result
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Invalid medication ID {medication_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise  # Re-raise HTTP exceptions
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to fetch medication {medication_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to fetch medication"
        )

@router.put(
    "/{medication_id}",
    response_model=MedicationInDB,
    summary="Update a medication"
)
async def update_medication(
    medication_id: int,
    update_data: MedicationUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Update a medication and its times.
    """
    start_time = time.time()
    request_id = f"update_med_{medication_id}_{int(start_time * 1000)}"
    
    logger.info(f"Request {request_id}: Updating medication {medication_id}")
    logger.debug(f"Request {request_id}: Update data: {update_data.dict(exclude_unset=True)}")
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        result = await medication_service.update_medication(medication_id, update_data)
        
        duration = time.time() - start_time
        if result:
            logger.info(
                f"Request {request_id}: Successfully updated medication '{result.name}' "
                f"(ID: {medication_id}) in {duration:.2f}s"
            )
        else:
            logger.warning(f"Request {request_id}: Medication {medication_id} not found for update")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Medication not found"
            )
            
        return result
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Validation failed for medication {medication_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to update medication {medication_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update medication"
        )

@router.put(
    "/bulk/{user_id}",
    response_model=List[MedicationInDB],
    summary="Bulk update user medications"
)
async def bulk_update_medications(
    user_id: int,
    medications_data: List[MedicationUpdate],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk update multiple medications for a user.
    """
    start_time = time.time()
    request_id = f"bulk_update_{user_id}_{int(start_time * 1000)}"
    
    logger.info(
        f"Request {request_id}: Starting bulk update for user {user_id} "
        f"with {len(medications_data)} medication updates"
    )
    
    try:
        medication_repo = MedicationRepository(db)
        medication_service = MedicationService(medication_repo)
        
        # Get user's current medications
        current_medications = await medication_service.get_user_medications(user_id)
        logger.debug(f"Request {request_id}: Found {len(current_medications)} current medications")
        
        updated_medications = []
        for medication in current_medications:
            # Find corresponding update data
            update_data = next((med for med in medications_data if getattr(med, 'id', None) == medication.id), None)
            if update_data:
                logger.debug(f"Request {request_id}: Updating medication {medication.id}")
                result = await medication_service.update_medication(medication.id, update_data)
                if result:
                    updated_medications.append(result)
        
        duration = time.time() - start_time
        logger.info(
            f"Request {request_id}: Successfully updated {len(updated_medications)} medications "
            f"for user {user_id} in {duration:.2f}s"
        )
        
        return updated_medications
        
    except ValueError as e:
        logger.warning(f"Request {request_id}: Validation failed for user {user_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Request {request_id}: Failed to bulk update medications for user {user_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update medications"
        )