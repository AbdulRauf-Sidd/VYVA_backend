import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import update, delete

from models.eleven_labs_batch_calls import ElevenLabsBatchCalls
from schemas.eleven_labs_batch_calls import (
    ElevenLabsBatchCallCreate, ElevenLabsBatchCallInDB
)

logger = logging.getLogger(__name__)


# -------- ElevenLabsBatchCalls --------

class ElevenLabsBatchCallRepository:
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session

    async def create(self, batch_call_data: ElevenLabsBatchCallCreate) -> ElevenLabsBatchCallInDB:
        """Create a new batch call"""
        try:
            batch_call = ElevenLabsBatchCalls(**batch_call_data.model_dump())
            self.db_session.add(batch_call)
            await self.db_session.flush()
            return ElevenLabsBatchCallInDB.model_validate(batch_call)
        except Exception as e:
            logger.error(f"Error creating batch call: {e}")
            raise

    async def get(self, batch_call_id: int) -> ElevenLabsBatchCallInDB | None:
        """Get a batch call by ID"""
        result = await self.db_session.execute(
            select(ElevenLabsBatchCalls).where(ElevenLabsBatchCalls.id == batch_call_id)
        )
        batch_call = result.scalar_one_or_none()
        return ElevenLabsBatchCallInDB.model_validate(batch_call) if batch_call else None


