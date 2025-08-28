from datetime import datetime
from pydantic import ConfigDict
from pydantic import BaseModel
from typing import Optional

class BrainCoachQuestionBase(BaseModel):
    session: int
    tier: int
    question_type: str
    question: str
    expected_answer: str
    scoring_logic: str
    theme: str

class BrainCoachQuestionCreate(BrainCoachQuestionBase):
    pass


class BrainCoachQuestionRead(BaseModel):
    id: int
    question_type: str
    question: str
    expected_answer: str
    scoring_logic: str
    theme: str

    model_config = ConfigDict(from_attributes=True)


class BrainCoachResponseBase(BaseModel):
    session_id: str
    user_id: Optional[int] = None  # Optional in development
    question_id: int
    user_answer: str
    score: int


class BrainCoachResponseCreate(BrainCoachResponseBase):
    pass


class BrainCoachResponseRead(BrainCoachResponseBase):
    id: int
    created: datetime

    model_config = ConfigDict(from_attributes=True)
