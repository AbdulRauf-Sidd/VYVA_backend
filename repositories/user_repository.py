"""
User repository for user-specific database operations.
"""

from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from models.user import User
from repositories.base import BaseRepository


class UserRepository(BaseRepository[User, None, None]):
    """User repository with user-specific operations."""
    
    def __init__(self, db: AsyncSession):
        super().__init__(User, db)
    
    async def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID."""
        query = select(User).where(User.id == user_id)
        result = await self.db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all active users."""
        query = select(User).where(User.is_active == True).offset(skip).limit(limit)
        result = await self.db.execute(query)
        return result.scalars().all()
    
    async def create_user(self, user: User) -> User:
        """Create a new user."""
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def update_user(self, user: User) -> User:
        """Update an existing user."""
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user
    
    async def email_exists(self, email: str) -> bool:
        """Check if email already exists."""
        query = select(User).where(User.email == email)
        result = await self.db.execute(query)
        return result.scalar_one_or_none() is not None
    
    async def get_users_by_role(self, is_superuser: bool = False) -> List[User]:
        """Get users by role."""
        query = select(User).where(User.is_superuser == is_superuser)
        result = await self.db.execute(query)
        return result.scalars().all() 