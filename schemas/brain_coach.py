from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime

# Base schemas
class QuestionTranslationBase(BaseModel):
    language: str
    question_text: str
    expected_answer: str
    scoring_logic: Optional[str] = None
    question_type: str
    theme: Optional[str] = None

class BrainCoachQuestionBase(BaseModel):
    session: int
    tier: int
    max_score: Optional[int] = 1
    category: Optional[str]

# Create schemas
class QuestionTranslationCreate(QuestionTranslationBase):
    question_id: int

class BrainCoachQuestionCreate(BrainCoachQuestionBase):
    translations: List[QuestionTranslationBase]

# Read schemas
class QuestionTranslationRead(QuestionTranslationBase):
    id: int
    question_id: int
    
    model_config = ConfigDict(from_attributes=True)

class BrainCoachQuestionRead(BrainCoachQuestionBase):
    id: int
    translations: List[QuestionTranslationRead]
    
    model_config = ConfigDict(from_attributes=True)

# For API responses with specific language
class BrainCoachQuestionReadWithLanguage(BrainCoachQuestionBase):
    id: int
    question_text: str
    expected_answer: str
    scoring_logic: Optional[str] = None
    question_type: str
    theme: Optional[str] = None
    language: str
    
    model_config = ConfigDict(from_attributes=True)


class BrainCoachResponseBase(BaseModel):
    session_id: Optional[str] = None  # Optional in development
    # user_id: Optional[int] = None  # Optional in development
    question_id: int
    user_answer: str
    score: int
    category: str


class BrainCoachResponseCreate(BrainCoachResponseBase):
    pass


class BrainCoachResponseRead(BaseModel):
    id: int
    created: datetime
    session_id: str
    question_id: int
    user_answer: str
    score: int

    model_config = ConfigDict(from_attributes=True)

class BrainCoachStatsRead(BaseModel):
    average_session_score: float
    total_sessions: int
    total_questions: int
    streak: int

class DailySessionActivity(BaseModel):
    date: str
    sessions: int

class DailySessionActivityResponse(BaseModel):
    trend: List[DailySessionActivity]
    
# class UserFeedback(BaseModel):
#     email: Optional[str] = None
#     phone_number: Optional[str] = None
#     name: Optional[str] = "N/A"
#     suggestions: Optional[str] = None
#     performance_tier: Optional[str] = None

#     class Config:
#         json_schema_extra = {
#             "example": {
#                 "email": "user@example.com",
#                 "phone_number": "+1234567890",
#                 "name": "Abdul Rauf Siddiqui",
#                 "suggestions": "Focus on improving the quiz interface.",
#                 "performance_tier": "On the Rise—Keep Going!"
#             }
#         }