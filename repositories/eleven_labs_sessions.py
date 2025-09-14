import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete

from models.eleven_labs_sessions import ElevenLabsSessions
from schemas.eleven_labs_session import (
    ElevenLabsSessionCreate, ElevenLabsSessionInDB
)

logger = logging.getLogger(__name__)

# -------- ElevenLabsSessions --------

class ElevenLabsSessionRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create(self, session_data: ElevenLabsSessionCreate) -> ElevenLabsSessionInDB:
        """Create a new session"""
        try:
            session = ElevenLabsSessions(**session_data.model_dump())
            self.db_session.add(session)
            await self.db_session.flush()
            return ElevenLabsSessionInDB.model_validate(session)
        except Exception as e:
            logger.error(f"Error creating session: {e}")
            raise

    async def get(self, session_id: int) -> ElevenLabsSessionInDB | None:
        """Get a session by ID"""
        result = await self.db_session.execute(
            select(ElevenLabsSessions).where(ElevenLabsSessions.id == session_id)
        )
        session = result.scalar_one_or_none()
        return ElevenLabsSessionInDB.model_validate(session) if session else None
