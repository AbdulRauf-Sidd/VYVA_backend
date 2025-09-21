from pydantic import BaseModel
from typing import Optional, List
from pydantic import field_validator

class NewsRequest(BaseModel):
    q: str  # Direct search query for SerpAPI (required)
    limit: Optional[int] = 3
    
    class Config:
        # Allow extra fields that might be sent by the agent
        extra = "ignore"
    
    @field_validator('limit', mode='before')
    @classmethod
    def validate_limit(cls, v):
        if isinstance(v, str):
            try:
                return int(v)
            except ValueError:
                return 3
        return v

class NewsResponse(BaseModel):
    success: bool
    stories: List[dict]
    total_count: int
    language: str
    locale: Optional[str] = None
    categories: Optional[List[str]] = None