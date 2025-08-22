"""
Text-to-Speech service for ElevenLabs integration.

Provides secure access to ElevenLabs TTS services with session management.
"""

import aiohttp
import json
from typing import Dict, Any, Optional
from core.config import settings
from core.logging import get_logger
from elevenlabs.client import ElevenLabs

logger = get_logger(__name__)

# Initialize the client
elevenlabs = ElevenLabs(api_key=settings.ELEVENLABS_API_KEY)

async def get_signed_url(agent_id: str):
    response = await elevenlabs.conversational_ai.conversations.get_signed_url(
        agent_id=agent_id
    )
    return response.signed_url

# class TTSService:
#     """Text-to-Speech service for ElevenLabs integration."""
    
#     def __init__(self):
#         self.api_key = settings.ELEVENLABS_API_KEY
#         self.base_url = settings.ELEVENLABS_BASE_URL
#         self.headers = {
#             "Accept": "application/json",
#             "xi-api-key": self.api_key
#         }

    
    
    # async def get_voices(self) -> list[Dict[str, Any]]:
    #     """Get available voices from ElevenLabs."""
    #     if not self.api_key:
    #         raise ValueError("ElevenLabs API key not configured")
        
    #     async with aiohttp.ClientSession() as session:
    #         async with session.get(
    #             f"{self.base_url}/v1/voices",
    #             headers=self.headers
    #         ) as response:
    #             if response.status == 200:
    #                 data = await response.json()
    #                 return data.get("voices", [])
    #             else:
    #                 error_text = await response.text()
    #                 logger.error(f"Failed to fetch voices: {error_text}")
    #                 raise Exception(f"Failed to fetch voices: {response.status}")
    
    # async def create_streaming_session(
    #     self,
    #     voice_id: str,
    #     text: str,
    #     model_id: str = "eleven_monolingual_v1",
    #     voice_settings: Optional[Dict[str, Any]] = None
    # ) -> Dict[str, Any]:
    #     """Create a streaming session for WebSocket TTS."""
    #     if not self.api_key:
    #         raise ValueError("ElevenLabs API key not configured")
        
    #     # Prepare request payload
    #     payload = {
    #         "text": text,
    #         "model_id": model_id,
    #         "voice_settings": voice_settings or {
    #             "stability": 0.5,
    #             "similarity_boost": 0.5
    #         }
    #     }
        
    #     async with aiohttp.ClientSession() as session:
    #         async with session.post(
    #             f"{self.base_url}/v1/text-to-speech/{voice_id}/stream",
    #             headers=self.headers,
    #             json=payload
    #         ) as response:
    #             if response.status == 200:
    #                 # For streaming, we return the WebSocket URL and session info
    #                 # In a real implementation, you might need to handle this differently
    #                 # based on ElevenLabs' actual streaming API
                    
    #                 session_data = {
    #                     "session_url": f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream",
    #                     "session_token": self.api_key,  # In production, generate a temporary token
    #                     "expires_in": 3600  # 1 hour
    #                 }
                    
    #                 logger.info(f"Created TTS streaming session for voice {voice_id}")
    #                 return session_data
    #             else:
    #                 error_text = await response.text()
    #                 logger.error(f"Failed to create streaming session: {error_text}")
    #                 raise Exception(f"Failed to create streaming session: {response.status}")
    
    # async def synthesize_speech(
    #     self,
    #     voice_id: str,
    #     text: str,
    #     model_id: str = "eleven_monolingual_v1",
    #     voice_settings: Optional[Dict[str, Any]] = None
    # ) -> bytes:
    #     """Synthesize speech and return audio data."""
    #     if not self.api_key:
    #         raise ValueError("ElevenLabs API key not configured")
        
    #     # Prepare request payload
    #     payload = {
    #         "text": text,
    #         "model_id": model_id,
    #         "voice_settings": voice_settings or {
    #             "stability": 0.5,
    #             "similarity_boost": 0.5
    #         }
    #     }
        
    #     async with aiohttp.ClientSession() as session:
    #         async with session.post(
    #             f"{self.base_url}/v1/text-to-speech/{voice_id}",
    #             headers=self.headers,
    #             json=payload
    #         ) as response:
    #             if response.status == 200:
    #                 audio_data = await response.read()
    #                 logger.info(f"Synthesized speech for voice {voice_id}")
    #                 return audio_data
    #             else:
    #                 error_text = await response.text()
    #                 logger.error(f"Failed to synthesize speech: {error_text}")
    #                 raise Exception(f"Failed to synthesize speech: {response.status}")
    
    # async def validate_voice_id(self, voice_id: str) -> bool:
    #     """Validate if a voice ID exists."""
    #     try:
    #         voices = await self.get_voices()
    #         return any(voice.get("voice_id") == voice_id for voice in voices)
    #     except Exception:
    #         return False 