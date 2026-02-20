from pydantic import BaseModel
from typing import Optional, List
from pydantic import field_validator

class NewsRequest(BaseModel):
    location: str
    topic: Optional[str] = "general"
    limit: Optional[int] = 5
    keywords: Optional[str] = None


class Article(BaseModel):
    title: str
    description: str
    source: str
    url: str
    publishedAt: str


class NewsResponse(BaseModel):
    ok: bool
    location: str
    topic: str
    count: int
    articles: List[Article]
    summary: str