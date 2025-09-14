from datetime import datetime
from pydantic import BaseModel, ConfigDict
from typing import Optional, Union, Dict, List
from sqlalchemy import JSON

# -------- ElevenLabsSessions --------

class ElevenLabsSessionBase(BaseModel):
    call_successful: Optional[str] = None
    user_id: Optional[int] = None
    agent_id: Optional[str] = None
    duration: Optional[int] = None
    termination_reason: Optional[str] = None
    summary: Optional[str] = None
    transcription: Optional[Union[str, List[Dict]]] = None


class ElevenLabsSessionCreate(ElevenLabsSessionBase):
    pass


class ElevenLabsSessionInDB(ElevenLabsSessionBase):
    id: int
    created: datetime

    model_config = ConfigDict(from_attributes=True)
