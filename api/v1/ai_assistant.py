"""
AI Assistant API endpoints.

Provides intelligent responses using OpenAI with web search capabilities for ElevenLabs voice consumption.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.config import settings
from services.ai_assistant_service import ai_assistant_service

logger = logging.getLogger(__name__)

router = APIRouter()


class AIAssistantRequest(BaseModel):
    """AI Assistant request schema."""
    question: str = Field(..., description="User's question", min_length=1, max_length=1000)
    include_web_search: bool = Field(True, description="Whether to include web search results")
    conversation_id: Optional[str] = Field(None, description="Optional conversation ID for tracking")


class AIAssistantResponse(BaseModel):
    """AI Assistant response schema - simplified for ElevenLabs consumption."""
    response: str = Field(..., description="Voice-optimized response")


@router.post("/ask", response_model=AIAssistantResponse)
async def ask_ai_assistant(
    request: AIAssistantRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Ask the AI assistant a question.
    
    This endpoint provides intelligent responses using OpenAI with optional web search.
    Responses are optimized for ElevenLabs voice synthesis.
    """
    try:
        logger.info(f"AI Assistant request received: {request.question[:50]}...")
        
        # Set default user context for healthcare application
        default_context = "You are a helpful AI assistant for a healthcare application called Vyva. The user is asking questions that may be related to health, technology, or general information. Provide clear, helpful responses optimized for voice synthesis."
        
        # Generate AI response
        ai_response = await ai_assistant_service.generate_response(
            question=request.question,
            user_context=default_context,
            include_web_search=request.include_web_search
        )
        
        logger.info(f"AI Assistant response generated successfully")
        return AIAssistantResponse(response=ai_response["response"])
        
    except Exception as e:
        logger.error(f"AI Assistant error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate AI response: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for AI Assistant service.
    """
    try:
        # Check if OpenAI is configured
        if not ai_assistant_service.openai_client or not settings.OPENAI_API_KEY:
            return {
                "status": "unhealthy",
                "message": "OpenAI API key not configured",
                "services": {
                    "openai": False,
                    "web_search": False
                }
            }
        
        return {
            "status": "healthy",
            "message": "AI Assistant service is operational",
            "services": {
                "openai": True,
                "web_search": True  # OpenAI handles web search natively
            }
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return {
            "status": "unhealthy",
            "message": f"Health check failed: {str(e)}",
            "services": {
                "openai": False,
                "web_search": False
            }
        }


@router.post("/test-voice-format")
async def test_voice_format(
    text: str = Query(..., description="Text to test voice formatting", min_length=1, max_length=1000)
):
    """
    Test voice formatting for a given text.
    
    This endpoint helps test how text will be formatted for ElevenLabs voice synthesis.
    """
    try:
        # Format text for voice
        voice_text = ai_assistant_service._clean_for_voice(text)
        duration = ai_assistant_service._estimate_speech_duration(voice_text)
        
        return {
            "original_text": text,
            "voice_formatted_text": voice_text,
            "estimated_speech_duration_seconds": duration,
            "character_count": len(voice_text),
            "word_count": len(voice_text.split())
        }
        
    except Exception as e:
        logger.error(f"Voice format test failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test voice formatting: {str(e)}"
        )
