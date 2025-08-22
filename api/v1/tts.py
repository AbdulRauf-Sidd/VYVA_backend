"""
Text-to-Speech API endpoints.

Provides secure access to ElevenLabs TTS services.
"""

from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from services.tts_service import get_signed_url
import logging


from core.database import get_db

# from core.security import get_current_active_user
# from models.user import User
# from services.tts_service import TTSService
# from schemas.common import SuccessResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/signed-url/{agent_id}")
async def signed_url(agent_id: str):
    try:
        logger.info(f"Request received for signed URL, agent_id={agent_id}")

        url = await get_signed_url(agent_id)

        if not url:
            logger.error(f"No signed URL returned for agent_id={agent_id}")
            raise HTTPException(status_code=404, detail="Signed URL not found")

        logger.info(f"Signed URL successfully generated for agent_id={agent_id}")
        return {"signed_url": url}

    except Exception as e:
        logger.error(f"Error while generating signed URL for agent_id={agent_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# class TTSSessionRequest(BaseModel):
#     """TTS session request schema."""
#     voice_id: str = Field(..., description="ElevenLabs voice ID")
#     text: str = Field(..., description="Text to convert to speech")
#     model_id: Optional[str] = Field(default="eleven_monolingual_v1", description="TTS model ID")
#     voice_settings: Optional[dict] = Field(default=None, description="Voice settings")


# class TTSSessionResponse(BaseModel):
#     """TTS session response schema."""
#     session_url: str = Field(..., description="WebSocket session URL")
#     session_token: str = Field(..., description="Session token for authentication")
#     expires_in: int = Field(..., description="Session expiration time in seconds")


# @router.post("/session", response_model=TTSSessionResponse)
# async def create_tts_session(
#     session_request: TTSSessionRequest,
#     current_user: User = Depends(get_current_active_user),
#     db: AsyncSession = Depends(get_db)
# ) -> Any:
#     """Create a secure TTS session for ElevenLabs WebSocket streaming."""
    
#     try:
#         tts_service = TTSService()
        
#         # Create a temporary session with ElevenLabs
#         session_data = await tts_service.create_streaming_session(
#             voice_id=session_request.voice_id,
#             text=session_request.text,
#             model_id=session_request.model_id,
#             voice_settings=session_request.voice_settings
#         )
        
#         return TTSSessionResponse(
#             session_url=session_data["session_url"],
#             session_token=session_data["session_token"],
#             expires_in=session_data["expires_in"]
#         )
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to create TTS session: {str(e)}"
#         )


# @router.get("/voices", response_model=dict)
# async def get_available_voices(
#     current_user: User = Depends(get_current_active_user)
# ) -> Any:
#     """Get available ElevenLabs voices."""
    
#     try:
#         tts_service = TTSService()
#         voices = await tts_service.get_voices()
#         return {"voices": voices}
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to fetch voices: {str(e)}"
#         )


# @router.post("/synthesize", response_model=dict)
# async def synthesize_speech(
#     synthesis_request: TTSSessionRequest,
#     current_user: User = Depends(get_current_active_user)
# ) -> Any:
#     """Synthesize speech and return audio data (for non-streaming use)."""
    
#     try:
#         tts_service = TTSService()
        
#         # Synthesize speech
#         audio_data = await tts_service.synthesize_speech(
#             voice_id=synthesis_request.voice_id,
#             text=synthesis_request.text,
#             model_id=synthesis_request.model_id,
#             voice_settings=synthesis_request.voice_settings
#         )
        
#         return {
#             "audio_data": audio_data,
#             "format": "mp3",
#             "sample_rate": 44100
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"Failed to synthesize speech: {str(e)}"
#         ) 