"""
Dependency injection utilities for API endpoints.
"""

from typing import AsyncGenerator
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from core.database import get_db
from core.security import get_current_user, get_current_active_user
from models.user import User


async def get_current_user_dependency(
    current_user: User = Depends(get_current_user)
) -> User:
    """Get current user dependency."""
    return current_user


async def get_current_active_user_dependency(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Get current active user dependency."""
    return current_user


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session dependency."""
    async for session in get_db():
        yield session


def require_superuser(current_user: User = Depends(get_current_active_user)) -> User:
    """Require superuser permissions."""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superuser privileges required"
        )
    return current_user 