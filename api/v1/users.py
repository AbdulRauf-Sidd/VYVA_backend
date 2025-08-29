from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from core.database import get_db
from schemas.user import UserCreate, UserRead, UserUpdate
from repositories.user import UserRepository

router = APIRouter()

@router.post(
    "/users", 
    response_model=UserRead, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new user",
    description="Create a new user with the provided details"
)
async def create_user(
    user: UserCreate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new user.
    
    - **email**: User's email address (required, must be unique)
    - **first_name**: User's first name (optional)
    - **last_name**: User's last name (optional)
    - **phone_number**: User's phone number (optional)
    - **age**: User's age (optional)
    - **living_situation**: User's living situation (optional)
    """
    repo = UserRepository(db)
    try:
        # Check if user already exists
        existing_user = await repo.get_user_by_email(user.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists"
            )
        
        return await repo.create_user(user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
        )

@router.get(
    "/{user_id}", 
    response_model=UserRead,
    summary="Get user by ID",
    description="Retrieve a user by their unique ID"
)
async def get_user(
    user_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Get a user by ID.
    
    - **user_id**: The unique identifier of the user
    """
    repo = UserRepository(db)
    try:
        user = await repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user: {str(e)}"
        )

@router.get(
    "/email/{email}", 
    response_model=UserRead,
    summary="Get user by email",
    description="Retrieve a user by their email address"
)
async def get_user_by_email(
    email: str, 
    db: AsyncSession = Depends(get_db)
):
    """
    Get a user by email.
    
    - **email**: The email address of the user
    """
    repo = UserRepository(db)
    try:
        user = await repo.get_user_by_email(email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with email {email} not found"
            )
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user: {str(e)}"
        )

@router.get(
    "/", 
    response_model=List[UserRead],
    summary="Get all users",
    description="Retrieve a list of all users with pagination support"
)
async def get_all_users(
    skip: int = 0, 
    limit: int = 100, 
    db: AsyncSession = Depends(get_db)
):
    """
    Get all users with pagination.
    
    - **skip**: Number of records to skip (for pagination)
    - **limit**: Maximum number of records to return (max 100)
    """
    repo = UserRepository(db)
    try:
        if limit > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit cannot exceed 100"
            )
        if skip < 0 or limit < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Skip must be >= 0 and limit must be >= 1"
            )
        
        return await repo.get_all_users(skip, limit)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve users: {str(e)}"
        )

@router.put(
    "/{user_id}", 
    response_model=UserRead,
    summary="Update user",
    description="Update an existing user's information"
)
async def update_user(
    user_id: int, 
    user_data: UserUpdate, 
    db: AsyncSession = Depends(get_db)
):
    """
    Update a user's information.
    
    - **user_id**: The unique identifier of the user to update
    - **user_data**: The updated user data (only provided fields will be updated)
    """
    repo = UserRepository(db)
    try:
        # Check if user exists first
        existing_user = await repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Check if email is being updated and if it's already taken
        if user_data.email:
            user_with_email = await repo.get_user_by_email(user_data.email)
            if user_with_email and user_with_email.id != user_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already in use by another user"
                )
        
        updated_user = await repo.update_user(user_id, user_data)
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found after update"
            )
        
        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )

@router.delete(
    "/{user_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete user",
    description="Permanently delete a user"
)
async def delete_user(
    user_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Delete a user.
    
    - **user_id**: The unique identifier of the user to delete
    """
    repo = UserRepository(db)
    try:
        # Check if user exists first
        existing_user = await repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        success = await repo.delete_user(user_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found for deletion"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete user: {str(e)}"
        )

@router.patch(
    "/{user_id}/deactivate", 
    response_model=UserRead,
    summary="Deactivate user",
    description="Deactivate a user (soft delete)"
)
async def deactivate_user(
    user_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Deactivate a user (soft delete).
    
    - **user_id**: The unique identifier of the user to deactivate
    """
    repo = UserRepository(db)
    try:
        # Check if user exists first
        existing_user = await repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Update user to set is_active=False
        updated_user = await repo.update_user(user_id, UserUpdate(is_active=False))
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found after deactivation"
            )
        
        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to deactivate user: {str(e)}"
        )

@router.patch(
    "/{user_id}/activate", 
    response_model=UserRead,
    summary="Activate user",
    description="Activate a previously deactivated user"
)
async def activate_user(
    user_id: int, 
    db: AsyncSession = Depends(get_db)
):
    """
    Activate a user.
    
    - **user_id**: The unique identifier of the user to activate
    """
    repo = UserRepository(db)
    try:
        # Check if user exists first
        existing_user = await repo.get_user_by_id(user_id)
        if not existing_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found"
            )
        
        # Update user to set is_active=True
        updated_user = await repo.update_user(user_id, UserUpdate(is_active=True))
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User with ID {user_id} not found after activation"
            )
        
        return updated_user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate user: {str(e)}"
        )