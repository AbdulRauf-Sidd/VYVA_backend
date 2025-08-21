"""
Authentication API endpoints.

Handles user login, token refresh, logout, and registration.
"""

from datetime import datetime, timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_token
)
from core.config import settings
from models.user import User
from repositories.user_repository import UserRepository
# from schemas.auth import (
#     UserLogin,
#     UserRegister,
#     TokenResponse,
#     TokenRefresh,
#     UserResponse,
#     PasswordResetRequest,
#     PasswordReset,
#     PasswordChange
# )
# from schemas.common import SuccessResponse

router = APIRouter()
security = HTTPBearer()


# @router.post("/login", response_model=TokenResponse)
# async def login(
#     user_credentials: UserLogin,
#     db: AsyncSession = Depends(get_db)
# ) -> Any:
#     """User login endpoint."""
#     user_repo = UserRepository(db)
#     user = await user_repo.get_by_email(user_credentials.email)
    
#     if not user or not verify_password(user_credentials.password, user.hashed_password):
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Incorrect email or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
    
#     if not user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Inactive user"
#         )
    
#     # Update last login
#     user.last_login = datetime.utcnow()
#     await db.commit()
    
#     # Create tokens
#     access_token = create_access_token(data={"sub": str(user.id)})
#     refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
#     return TokenResponse(
#         access_token=access_token,
#         refresh_token=refresh_token,
#         token_type="bearer",
#         expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
#     )


# @router.post("/register", response_model=UserResponse)
# async def register(
#     user_data: UserRegister,
#     db: AsyncSession = Depends(get_db)
# ) -> Any:
#     """User registration endpoint."""
#     user_repo = UserRepository(db)
    
#     # Check if user already exists
#     existing_user = await user_repo.get_by_email(user_data.email)
#     if existing_user:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Email already registered"
#         )
    
#     # Create new user
#     hashed_password = get_password_hash(user_data.password)
#     user = User(
#         email=user_data.email,
#         hashed_password=hashed_password,
#         first_name=user_data.first_name,
#         last_name=user_data.last_name,
#         phone_number=user_data.phone_number
#     )
    
#     created_user = await user_repo.create(user)
#     return UserResponse.from_orm(created_user)


# @router.post("/refresh", response_model=TokenResponse)
# async def refresh_token(
#     token_data: TokenRefresh,
#     db: AsyncSession = Depends(get_db)
# ) -> Any:
#     """Refresh access token endpoint."""
#     try:
#         payload = verify_token(token_data.refresh_token)
#         if payload.get("type") != "refresh":
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid token type"
#             )
        
#         user_id = payload.get("sub")
#         if not user_id:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="Invalid token"
#             )
        
#         user_repo = UserRepository(db)
#         user = await user_repo.get_by_id(int(user_id))
        
#         if not user or not user.is_active:
#             raise HTTPException(
#                 status_code=status.HTTP_401_UNAUTHORIZED,
#                 detail="User not found or inactive"
#             )
        
#         # Create new tokens
#         access_token = create_access_token(data={"sub": str(user.id)})
#         refresh_token = create_refresh_token(data={"sub": str(user.id)})
        
#         return TokenResponse(
#             access_token=access_token,
#             refresh_token=refresh_token,
#             token_type="bearer",
#             expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
#         )
        
#     except HTTPException:
#         raise
#     except Exception:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid refresh token"
#         )


# @router.post("/logout", response_model=SuccessResponse)
# async def logout(
#     credentials: HTTPBearer = Depends(security),
#     db: AsyncSession = Depends(get_db)
# ) -> Any:
#     """User logout endpoint."""
#     # In a real implementation, you might want to:
#     # 1. Add the refresh token to a blacklist
#     # 2. Log the logout event
#     # 3. Clear any session data
    
#     return SuccessResponse(message="Successfully logged out")


# @router.post("/password-reset-request", response_model=SuccessResponse)
# async def request_password_reset(
#     reset_request: PasswordResetRequest,
#     db: AsyncSession = Depends(get_db)
# ) -> Any:
#     """Request password reset endpoint."""
#     user_repo = UserRepository(db)
#     user = await user_repo.get_by_email(reset_request.email)
    
#     if user:
#         # In a real implementation, you would:
#         # 1. Generate a password reset token
#         # 2. Send an email with the reset link
#         # 3. Store the token with expiration
        
#         # For now, just return success
#         pass
    
#     # Always return success to prevent email enumeration
#     return SuccessResponse(
#         message="If the email exists, a password reset link has been sent"
#     )


# @router.post("/password-reset", response_model=SuccessResponse)
# async def reset_password(
#     reset_data: PasswordReset,
#     db: AsyncSession = Depends(get_db)
# ) -> Any:
#     """Reset password endpoint."""
#     # In a real implementation, you would:
#     # 1. Verify the reset token
#     # 2. Update the user's password
#     # 3. Invalidate the reset token
    
#     return SuccessResponse(message="Password successfully reset")


# @router.post("/change-password", response_model=SuccessResponse)
# async def change_password(
#     password_data: PasswordChange,
#     current_user: User = Depends(get_current_user_dependency),
#     db: AsyncSession = Depends(get_db)
# ) -> Any:
#     """Change password endpoint."""
#     if not verify_password(password_data.current_password, current_user.hashed_password):
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,
#             detail="Incorrect current password"
#         )
    
#     # Update password
#     current_user.hashed_password = get_password_hash(password_data.new_password)
#     await db.commit()
    
#     return SuccessResponse(message="Password successfully changed")


# # Dependency for current user
# async def get_current_user_dependency(
#     credentials: HTTPBearer = Depends(security),
#     db: AsyncSession = Depends(get_db)
# ) -> User:
#     """Get current user dependency."""
#     token = credentials.credentials
#     payload = verify_token(token)
    
#     if payload.get("type") != "access":
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token type"
#         )
    
#     user_id = payload.get("sub")
#     if not user_id:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid token"
#         )
    
#     user_repo = UserRepository(db)
#     user = await user_repo.get_by_id(int(user_id))
    
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="User not found"
#         )
    
#     return user 