# """
# User schemas for user management operations.
# """

# from datetime import datetime
# from typing import Optional
# from pydantic import BaseModel, Field, EmailStr

# from .common import BaseSchema


# class UserCreate(BaseModel):
#     """User creation schema."""
#     email: EmailStr = Field(..., description="User email")
#     password: str = Field(..., min_length=6, description="User password")
#     first_name: Optional[str] = Field(None, max_length=100, description="First name")
#     last_name: Optional[str] = Field(None, max_length=100, description="Last name")
#     phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
#     is_active: bool = Field(default=True, description="User active status")
#     is_superuser: bool = Field(default=False, description="Superuser status")


# class UserUpdate(BaseModel):
#     """User update schema."""
#     first_name: Optional[str] = Field(None, max_length=100, description="First name")
#     last_name: Optional[str] = Field(None, max_length=100, description="Last name")
#     phone_number: Optional[str] = Field(None, max_length=20, description="Phone number")
#     is_active: Optional[bool] = Field(None, description="User active status")
#     is_verified: Optional[bool] = Field(None, description="User verification status")


# class UserResponse(BaseSchema):
#     """User response schema."""
#     id: int
#     email: str
#     first_name: Optional[str]
#     last_name: Optional[str]
#     phone_number: Optional[str]
#     is_active: bool
#     is_verified: bool
#     is_superuser: bool
#     created_at: datetime
#     updated_at: Optional[datetime]
#     last_login: Optional[datetime]


# class UserListResponse(BaseSchema):
#     """User list response schema."""
#     id: int
#     email: str
#     first_name: Optional[str]
#     last_name: Optional[str]
#     is_active: bool
#     is_verified: bool
#     created_at: datetime
#     last_login: Optional[datetime] 