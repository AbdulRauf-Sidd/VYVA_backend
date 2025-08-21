"""
Common schemas used across the application.
"""

from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, Field


class BaseSchema(BaseModel):
    """Base schema with common fields."""
    
    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


# class PaginationParams(BaseModel):
#     """Pagination parameters for list endpoints."""
#     page: int = Field(default=1, ge=1, description="Page number")
#     size: int = Field(default=20, ge=1, le=100, description="Page size")
#     sort_by: Optional[str] = Field(default="created_at", description="Sort field")
#     sort_order: Optional[str] = Field(default="desc", description="Sort order (asc/desc)")


# class PaginatedResponse(BaseModel):
#     """Paginated response wrapper."""
#     items: list[Any]
#     total: int
#     page: int
#     size: int
#     pages: int
    
#     @classmethod
#     def create(cls, items: list[Any], total: int, page: int, size: int):
#         """Create a paginated response."""
#         pages = (total + size - 1) // size
#         return cls(
#             items=items,
#             total=total,
#             page=page,
#             size=size,
#             pages=pages
#         )


# class ErrorResponse(BaseModel):
#     """Error response schema."""
#     detail: str
#     error_code: Optional[str] = None
#     field_errors: Optional[Dict[str, str]] = None


# class SuccessResponse(BaseModel):
#     """Success response schema."""
#     message: str
#     data: Optional[Any] = None


# class HealthCheckResponse(BaseModel):
#     """Health check response schema."""
#     status: str
#     service: str
#     version: str
#     timestamp: datetime = Field(default_factory=datetime.utcnow) 