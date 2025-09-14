from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func
from core.database import Base


class ElevenLabsBatchCalls(Base):
    __tablename__ = "eleven_labs_batch_calls"

    id = Column(Integer, primary_key=True, index=True)
    batch_id = Column(String(30), nullable=False)
    checked = Column(Boolean, default=False)
    created = Column(DateTime(timezone=True), server_default=func.now())