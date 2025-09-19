"""
AI Assistant schemas for request and response models.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from pydantic import ConfigDict


class AIAssistantRequest(BaseModel):
    """AI Assistant request schema."""
    question: str = Field(..., description="User's question", min_length=1, max_length=1000)
    include_web_search: bool = Field(True, description="Whether to include web search results")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for tracking")
    
    model_config = ConfigDict(from_attributes=True)


class WebSearchResult(BaseModel):
    """Web search result schema."""
    title: str = Field(..., description="Search result title")
    snippet: str = Field(..., description="Search result snippet")
    link: str = Field(..., description="Search result URL")
    
    model_config = ConfigDict(from_attributes=True)


class AIAssistantResponse(BaseModel):
    """AI Assistant response schema."""
    response: str = Field(..., description="Voice-optimized response")
    original_response: str = Field(..., description="Original AI response")
    web_search_used: bool = Field(..., description="Whether web search was used")
    web_results: List[WebSearchResult] = Field(default=[], description="Web search results if used")
    format: str = Field(..., description="Response format type")
    length: int = Field(..., description="Response length in characters")
    estimated_speech_duration: int = Field(..., description="Estimated speech duration in seconds")
    conversation_id: Optional[str] = Field(None, description="Conversation ID if provided")
    error: Optional[bool] = Field(False, description="Whether an error occurred")
    
    model_config = ConfigDict(from_attributes=True)


class VoiceFormatTestRequest(BaseModel):
    """Voice format test request schema."""
    text: str = Field(..., description="Text to test voice formatting", min_length=1, max_length=1000)
    
    model_config = ConfigDict(from_attributes=True)


class VoiceFormatTestResponse(BaseModel):
    """Voice format test response schema."""
    original_text: str = Field(..., description="Original input text")
    voice_formatted_text: str = Field(..., description="Voice-optimized text")
    estimated_speech_duration_seconds: int = Field(..., description="Estimated speech duration")
    character_count: int = Field(..., description="Character count")
    word_count: int = Field(..., description="Word count")
    
    model_config = ConfigDict(from_attributes=True)


class HealthCheckResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(..., description="Service status")
    message: str = Field(..., description="Status message")
    services: Dict[str, bool] = Field(..., description="Service availability status")
    
    model_config = ConfigDict(from_attributes=True)
