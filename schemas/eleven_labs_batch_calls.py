from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional


# -------- ElevenLabsBatchCalls --------

class ElevenLabsBatchCallBase(BaseModel):
    batch_id: str


class ElevenLabsBatchCallCreate(ElevenLabsBatchCallBase):
    pass


class ElevenLabsBatchCallInDB(ElevenLabsBatchCallBase):
    id: int
    checked: bool
    created: datetime

    model_config = ConfigDict(from_attributes=True)


