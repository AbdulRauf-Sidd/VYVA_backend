"""
Users API endpoints.

Handles user management operations.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_active_user
from models.user import User
from repositories.user_repository import UserRepository
# from schemas.user import UserResponse, UserUpdate
# from schemas.common import PaginatedResponse, PaginationParams

router = APIRouter()


# @router.get("/me", response_model=UserResponse)
# async def get_current_user(
#     current_user: User = Depends(get_current_active_user)
# ) -> UserResponse:
#     """Get current user information."""
#     return UserResponse.from_orm(current_user)


# @router.put("/me", response_model=UserResponse)
# async def update_current_user(
#     user_update: UserUpdate,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ) -> UserResponse:
#     """Update current user information."""
#     user_repo = UserRepository(db)
    
#     # Update user fields
#     for field, value in user_update.dict(exclude_unset=True).items():
#         setattr(current_user, field, value)
    
#     updated_user = await user_repo.update_user(current_user)
#     return UserResponse.from_orm(updated_user)


# @router.get("/", response_model=PaginatedResponse)
# async def get_users(
#     pagination: PaginationParams = Depends(),
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ) -> PaginatedResponse:
#     """Get paginated list of users (admin only)."""
#     if not current_user.is_superuser:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="Superuser privileges required"
#         )
    
#     user_repo = UserRepository(db)
#     skip = (pagination.page - 1) * pagination.size
    
#     users = await user_repo.get_multi(skip=skip, limit=pagination.size)
#     total = await user_repo.count()
    
#     return PaginatedResponse.create(
#         items=[UserResponse.from_orm(user) for user in users],
#         total=total,
#         page=pagination.page,
#         size=pagination.size
#     ) 