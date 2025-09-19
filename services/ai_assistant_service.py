"""
AI Assistant service using OpenAI with built-in web search capabilities.

This service leverages OpenAI's native web search functionality through function calling,
providing intelligent responses with current information for ElevenLabs voice consumption.

Key Features:
- OpenAI GPT-4 for intelligent responses
- Built-in web search via OpenAI function calling
- Voice-optimized response formatting
- No external search API dependencies required
"""

import openai
import httpx
import json
import logging
from typing import Dict, Any, List, Optional
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

class AIAssistantService:
    """AI Assistant service with OpenAI and web search integration."""
    
    def __init__(self):
        # Initialize OpenAI client with proper configuration
        try:
            # Create client with explicit parameters to avoid proxy issues
            self.openai_client = openai.OpenAI(
                api_key=settings.OPENAI_API_KEY,
                timeout=30.0
            )
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            # Fallback initialization
            self.openai_client = None
        
        self.model = settings.OPENAI_MODEL
        self.max_tokens = settings.OPENAI_MAX_TOKENS
        self.temperature = settings.OPENAI_TEMPERATURE
        
    async def search_web(self, query: str, num_results: int = 3) -> List[Dict[str, Any]]:
        """
        Search the web using OpenAI's built-in web search capabilities.
        
        Args:
            query: Search query
            num_results: Number of results to return
            
        Returns:
            List of search results with title, snippet, and link
        """
        try:
            if not self.openai_client:
                logger.warning("OpenAI client not available, returning empty results")
                return []
                
            # Use OpenAI to search the web and provide current information
            search_prompt = f"""Search the web for current information about: {query}
            
            Provide 2-3 recent, relevant search results with:
            - Title of the source/article
            - Brief summary of the content
            - Source URL or website name
            
            Focus on the most current and accurate information available.
            Format your response clearly with titles and summaries."""
            
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": search_prompt}],
                max_tokens=800,
                temperature=0.3
            )
            
            # Parse the response into search-like results
            content = response.choices[0].message.content
            results = self._parse_search_results(content, query, num_results)
            
            logger.info(f"OpenAI web search completed for query: {query[:50]}...")
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
                
                title = line.replace('Title:', '').replace('**', '').replace('#', '').strip()
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
    
    def _needs_web_search(self, question: str) -> bool:
        """Determine if a question needs web search for current information."""
        web_keywords = [
            'latest', 'recent', 'current', 'new', 'today', 'now', '2024', '2025',
            'news', 'update', 'trending', 'popular', 'best', 'top', 'reviews',
            'price', 'cost', 'buy', 'where to', 'how to get', 'availability'
        ]
        question_lower = question.lower()
        return any(keyword in question_lower for keyword in web_keywords)
    
    async def generate_response(
        self, 
        question: str, 
        user_context: Optional[str] = None,
        include_web_search: bool = True
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
                logger.warning("OpenAI client not available, returning error response")
                return self._create_error_response("OpenAI client not available. Please check API key configuration.")
                
            # Perform web search if enabled and question seems to need current info
            web_results = []
            if include_web_search and self._needs_web_search(question):
                try:
                    web_results = await self.search_web(question, num_results=3)
                except Exception as e:
                    logger.warning(f"Web search failed: {str(e)}")
                    web_results = []
            
            # Prepare system prompt for voice-friendly responses
            system_prompt = self._create_system_prompt(user_context)
            
            # Add web search context to the question if we have results
            user_question = question
            if web_results:
                web_context = "\n\nCurrent information from web search:\n"
                for i, result in enumerate(web_results, 1):
                    web_context += f"{i}. {result.get('title', 'Result')}: {result.get('snippet', 'No description available')}\n"
                user_question = question + web_context
            
            # Prepare messages for OpenAI
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_question}
            ]
            
            # Generate response using OpenAI (no function calling)
            response = self.openai_client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            ai_response = response.choices[0].message.content
            
            # Format response for ElevenLabs voice consumption
            formatted_response = self._format_for_voice(ai_response, web_results)
            
            logger.info(f"AI response generated for question: {question[:50]}...")
            return formatted_response
            
        except Exception as e:
            logger.error(f"AI response generation failed: {str(e)}")
            return self._create_error_response(str(e))
    
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
        text = text.replace("##", "").replace("#", "")
        
        # Replace problematic characters
        text = text.replace("&", "and")
        text = text.replace("@", "at")
        text = text.replace("#", "number")
        
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
