"""
AI Assistant service using OpenAI Responses API with optional web search and concierge (Google Places).

Key features:
- OpenAI Responses API for robust text generation
- Optional real web search (SERP provider) for current info
- Optional Google Places concierge lookups (text search + details)
- Voice-optimized response formatting for ElevenLabs
"""

from openai import OpenAI
import logging
import json
from typing import Dict, Any, List, Optional
from core.config import settings
from core.logging import get_logger
from .google_places_service import google_places

logger = get_logger(__name__)


class AIAssistantService:
    """AI Assistant service with OpenAI and web search integration."""

    def __init__(self):
        # Initialize OpenAI client with proper configuration
        try:
            # Initialize Responses API client
            self.openai_client = OpenAI(
                api_key=settings.OPENAI_API_KEY,
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            # Fallback initialization
            self.openai_client = None

        # Safe defaults
        self.model = settings.OPENAI_MODEL or "gpt-4o-mini"
        self.max_tokens = int(settings.OPENAI_MAX_TOKENS or 300)
        self.temperature = float(settings.OPENAI_TEMPERATURE or 0.5)

    def _supports_responses_api(self) -> bool:
        """Return True if the installed OpenAI SDK exposes the Responses API."""
        try:
            return bool(getattr(self.openai_client, "responses", None))
        except Exception:
            return False

    async def search_web(self, query: str, num_results: int = 3) -> List[Dict[str, Any]]:
        """
        Search the web using OpenAI Responses API web tool when available.
        Fall back to an LLM-only summary if the web tool isn't supported.
        """
        if not self.openai_client:
            logger.warning(
                "OpenAI client not available, returning empty results")
            return []
        try:
            if self._supports_responses_api():
                sys = (
                    "You can search the web. Return ONLY JSON: an array of up to "
                    f"{num_results} objects with fields title, snippet, and link."
                )
                user = f"Search the web and extract current, trustworthy results for: {query}"
                response = self.openai_client.responses.create(
                    model=self.model,
                    input=[
                        {"role": "system", "content": sys},
                        {"role": "user", "content": user},
                    ],
                    tools=[{"type": "web_search"}],
                    tool_choice="auto",
                    max_output_tokens=500,
                    temperature=0.2,
                )
                content = response.output_text
            else:
                # Fallback: ask the model to synthesize search-like results (no live browsing)
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "Return ONLY JSON: an array (max "
                            f"{num_results}) with objects having fields title, snippet, and link."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Provide up-to-date information for: {query}. Include source/site names when possible.",
                    },
                ]
                chat = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=0.2,
                )
                content = (chat.choices[0].message.content or "").strip() or "[]"
            results: List[Dict[str, Any]] = []
            try:
                parsed = json.loads(content)
                if isinstance(parsed, list):
                    for item in parsed[:num_results]:
                        results.append({
                            "title": (item.get("title") if isinstance(item, dict) else str(item)) or "Result",
                            "snippet": (item.get("snippet") if isinstance(item, dict) else "") or "",
                            "link": (item.get("link") if isinstance(item, dict) else "") or "",
                        })
                else:
                    results = self._parse_search_results(
                        content, query, num_results)
            except Exception:
                results = self._parse_search_results(
                    content, query, num_results)

            logger.info(
                f"OpenAI web search completed for query: {query[:50]}...")
            return results
        except Exception as e:
            logger.error(f"OpenAI web search failed: {str(e)}")
            return []

    def _parse_search_results(self, content: str, query: str, num_results: int = 3) -> List[Dict[str, Any]]:
        """Parse OpenAI response into search-like results."""
        lines = content.split('\n')
        results = []
        current_result = {}

        for line in lines:
            line = line.strip()
            # Look for titles (various formats)
            if (line.startswith('Title:') or line.startswith('**') or
                    line.startswith('#') or (line.isupper() and len(line) > 10)):

                if current_result:
                    results.append(current_result)

                title = line.replace('Title:', '').replace(
                    '**', '').replace('#', '').strip()
                current_result = {
                    "title": title,
                    "snippet": "",
                    "link": f"Web Search Result - {query}"
                }
            elif line and current_result and not line.startswith('Title:') and not line.startswith('**'):
                current_result["snippet"] += line + " "

        if current_result:
            results.append(current_result)

        # If parsing failed, create a simple result
        if not results:
            results = [{
                "title": f"Current Information about {query}",
                "snippet": content[:300] + "..." if len(content) > 300 else content,
                "link": "Web Search"
            }]

        return results[:num_results]  # Limit to requested number of results

    async def concierge_places(
        self,
        query: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        radius_meters: Optional[int] = 3000,
        with_details: bool = False,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Search nearby places and optionally fetch details for each place."""
        location = None
        if latitude is not None and longitude is not None:
            location = (latitude, longitude)
        summaries = await google_places.text_search(
            query=query, location=location, radius_meters=radius_meters, max_results=max_results
        )
        if not with_details:
            return {"results": summaries}
        detailed: List[Dict[str, Any]] = []
        for s in summaries:
            pid = s.get("place_id")
            if not pid:
                detailed.append(s)
                continue
            details = await google_places.place_details(pid)
            detailed.append(details or s)
        return {"results": detailed}

    def _needs_web_search(self, question: str) -> bool:
        """Determine if a question needs web search for current information."""
        web_keywords = [
            'latest', 'recent', 'current', 'new', 'today', 'now', '2024', '2025',
            'news', 'update', 'trending', 'popular', 'best', 'top', 'reviews',
            'price', 'cost', 'buy', 'where to', 'how to get', 'availability',
            # travel keywords
            'flight', 'flights', 'airline', 'airport', 'train', 'trains', 'rail',
            'schedule', 'schedules', 'timetable', 'timetables', 'fare', 'fares',
            'ticket', 'tickets', 'route', 'routes', 'bus', 'buses', 'itinerary'
        ]
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in web_keywords)

    async def generate_response(
        self,
        question: str,
        user_context: Optional[str] = None,
        include_web_search: bool = True,
        conversation_id: Optional[str] = None,
        force_web: bool = False,
    ) -> Dict[str, Any]:
        """
        Generate AI response using OpenAI with optional web search.

        Args:
            question: User's question
            user_context: Optional context about the user
            include_web_search: Whether to include web search results

        Returns:
            Formatted response for ElevenLabs voice consumption
        """
        try:
            if not self.openai_client:
                logger.warning(
                    "OpenAI client not available, returning error response")
                return self._create_error_response("OpenAI client not available. Please check API key configuration.")

            # Optionally prefetch web results only when force_web is true and Responses API is supported
            web_results: List[Dict[str, Any]] = []
            if include_web_search and force_web and self._supports_responses_api():
                try:
                    web_results = await self.search_web(question, num_results=3)
                except Exception as e:
                    logger.warning(f"Prefetch web search failed: {str(e)}")
                    web_results = []

            # Prepare system prompt for voice-friendly responses
            system_prompt = self._create_system_prompt(user_context)

            # Add gentle instruction to browse when necessary
            if include_web_search and force_web and self._supports_responses_api():
                system_prompt += "\n\nWhen answering, you MUST use the web_search tool to verify the latest information before responding."
            elif include_web_search:
                system_prompt += "\n\nWhen information may be time-sensitive or uncertain, you MAY use the web_search tool to verify before responding."

            # Generate response using OpenAI; expose web_search tool with auto selection when enabled
            create_kwargs: Dict[str, Any] = {
                "model": self.model,
                "input": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ],
                "max_output_tokens": self.max_tokens,
                "temperature": self.temperature,
            }
            if include_web_search and self._supports_responses_api():
                create_kwargs.update({
                    "tools": [{"type": "web_search"}],
                    "tool_choice": "auto",
                })

            if self._supports_responses_api():
                response = self.openai_client.responses.create(**create_kwargs)
                ai_response = response.output_text
            else:
                # Fallback to chat completions without web tool
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question},
                ]
                chat = self.openai_client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                )
                ai_response = chat.choices[0].message.content or ""

            # Format response for ElevenLabs voice consumption
            formatted_response = self._format_for_voice(
                ai_response, web_results)
            if conversation_id:
                formatted_response["conversation_id"] = conversation_id

            logger.info(
                f"AI response generated for question: {question[:50]}...")
            return formatted_response

        except Exception as e:
            logger.error(f"AI response generation failed: {str(e)}")
            err = self._create_error_response(str(e))
            if conversation_id:
                err["conversation_id"] = conversation_id
            return err

    def _create_system_prompt(self, user_context: Optional[str]) -> str:
        """Create system prompt for OpenAI with web search context."""

        prompt = """You are a helpful AI assistant designed to provide clear, conversational responses that will be converted to speech by ElevenLabs voice synthesis.

IMPORTANT FORMATTING GUIDELINES FOR VOICE:
- Keep responses concise and conversational (2-3 sentences max)
- Use simple, clear language
- Avoid complex punctuation that doesn't work well in speech
- Use natural pauses indicated by periods
- Avoid bullet points or numbered lists - use "first", "second", "then" instead
- Make responses sound natural when spoken aloud

Your role is to answer questions helpfully and accurately. You have access to web search capabilities to find current information when needed."""

        if user_context:
            prompt += f"\n\nUSER CONTEXT: {user_context}"

        return prompt

    def _format_for_voice(self, ai_response: str, web_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Format the response for ElevenLabs voice consumption."""

        # Clean up the response for voice synthesis
        voice_text = self._clean_for_voice(ai_response)

        return {
            "response": voice_text,
            "original_response": ai_response,
            "web_search_used": len(web_results) > 0,
            "web_results": web_results,
            "format": "voice_optimized",
            "length": len(voice_text),
            "estimated_speech_duration": self._estimate_speech_duration(voice_text)
        }

    def _clean_for_voice(self, text: str) -> str:
        """Clean text for optimal voice synthesis."""
        # Remove markdown formatting
        text = text.replace("**", "").replace("*", "")
        text = text.replace("##", "")

        # Replace problematic characters
        text = text.replace("&", "and")
        text = text.replace("@", "at")

        # Ensure proper sentence endings
        if not text.endswith(('.', '!', '?')):
            text += "."

        return text.strip()

    def _estimate_speech_duration(self, text: str) -> int:
        """Estimate speech duration in seconds (rough estimate)."""
        # Average speaking rate is about 150-160 words per minute
        words = len(text.split())
        return max(1, int(words / 2.5))  # Conservative estimate

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create error response for voice consumption."""
        return {
            "response": "I apologize, but I'm having trouble processing your request right now. Please try again in a moment.",
            "original_response": f"Error: {error_message}",
            "web_search_used": False,
            "web_results": [],
            "format": "voice_optimized",
            "length": 0,
            "estimated_speech_duration": 5,
            "error": True
        }


# Create service instance
ai_assistant_service = AIAssistantService()
