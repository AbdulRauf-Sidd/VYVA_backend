# """
# Authentication schemas for login, registration, and token management.
# """

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class UserLogin(BaseModel):
    """User login request schema."""
    email: EmailStr = Field(..., description="User email")
    password: str = Field(..., min_length=6, description="User password")


# class UserRegister(BaseModel):
#     """User registration request schema."""
#     email: EmailStr = Field(..., description="User email")
#     password: str = Field(..., min_length=6, description="User password")
#     first_name: Optional[str] = Field(None, max_length=100, description="First name")
#     last_name: Optional[str] = Field(None, max_length=100, description="Last name")
#     phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")


# class TokenResponse(BaseModel):
#     """Token response schema."""
#     access_token: str = Field(..., description="JWT access token")
#     refresh_token: str = Field(..., description="JWT refresh token")
#     token_type: str = Field(default="bearer", description="Token type")
#     expires_in: int = Field(..., description="Access token expiration time in seconds")


# class TokenRefresh(BaseModel):
#     """Token refresh request schema."""
#     refresh_token: str = Field(..., description="JWT refresh token")


# class PasswordResetRequest(BaseModel):
#     """Password reset request schema."""
#     email: EmailStr = Field(..., description="User email")


# class PasswordReset(BaseModel):
#     """Password reset schema."""
#     token: str = Field(..., description="Password reset token")
#     new_password: str = Field(..., min_length=6, description="New password")


# class PasswordChange(BaseModel):
#     """Password change schema."""
#     current_password: str = Field(..., description="Current password")
#     new_password: str = Field(..., min_length=6, description="New password")


# class UserResponse(BaseSchema):
#     """User response schema."""
#     id: int
#     email: str
#     first_name: Optional[str]
#     last_name: Optional[str]
#     phone_number: Optional[str]
#     is_active: bool
#     is_verified: bool
#     created_at: datetime
#     last_login: Optional[datetime]
    
#     class Config:
#         from_attributes = True 