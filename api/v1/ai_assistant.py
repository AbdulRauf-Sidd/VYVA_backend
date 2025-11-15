"""
AI Assistant API endpoints.

Provides intelligent responses using OpenAI with web search capabilities for ElevenLabs voice consumption.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from typing import Optional
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from core.config import settings
from services.ai_assistant_service import ai_assistant_service
from services.google_places_service import google_places
from schemas.ai_assistant import (
    AIAssistantRequest,
    AIAssistantResponse,
    VoiceFormatTestResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


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
            include_web_search=request.include_web_search,
            conversation_id=request.conversation_id,
        )
        
        logger.info(f"AI Assistant response generated successfully")
        # Return full response payload per schema
        return AIAssistantResponse(**ai_response)
        
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
        # Reflect actual configured services
        workflow_ready = bool(ai_assistant_service.workflow_engine and settings.OPENAI_API_KEY)
        supports_web_tool = bool(
            workflow_ready and ai_assistant_service.workflow_engine and ai_assistant_service.workflow_engine.supports_web_tool
        )
        web_ok = workflow_ready and supports_web_tool
        places_ok = bool(google_places._is_enabled())
        status_text = "healthy" if workflow_ready else "unhealthy"
        message = "AI Assistant service is operational" if workflow_ready else "OpenAI workflow not configured"
        return {
            "status": status_text,
            "message": message,
            "services": {
                "openai": workflow_ready,
                "web_search": web_ok,
                "google_places": places_ok,
            },
            "model": getattr(ai_assistant_service, "model", None),
            "web_tool_available": supports_web_tool
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


@router.post("/test-voice-format", response_model=VoiceFormatTestResponse)
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
            "word_count": len(voice_text.split()),
        }
        
    except Exception as e:
        logger.error(f"Voice format test failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test voice formatting: {str(e)}"
        )
