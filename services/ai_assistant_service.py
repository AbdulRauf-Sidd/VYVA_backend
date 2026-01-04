"""
AI Assistant service using OpenAI Workflows/Agents SDK with optional web search
and concierge (Google Places).

Key features:
- OpenAI Agents/Workflows SDK for robust text generation
- Optional real web search (web_search_preview tool) for current info
- Optional Google Places concierge lookups (text search + details)
- Voice-optimized response formatting for ElevenLabs
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from core.config import settings
from core.logging import get_logger
from .google_places_service import google_places

try:
    from agents import (  # type: ignore[import]
        Agent,
        ModelSettings,
        Runner,
        RunConfig,
        WebSearchTool,
        trace,
        TResponseInputItem,
    )
    from openai.types.shared.reasoning import Reasoning

    AGENT_SDK_AVAILABLE = True
except ImportError:
    AGENT_SDK_AVAILABLE = False
    Agent = ModelSettings = Runner = RunConfig = WebSearchTool = trace = None  # type: ignore
    Reasoning = None  # type: ignore

logger = get_logger(__name__)

DEFAULT_AGENT_INSTRUCTIONS = (
    "You are a helpful, gentle, kind, and calm assistant designed to support seniors. "
    "Respond to their queries with patience and clarity. Whenever necessary, search the web "
    "to provide accurate and up-to-date information. Always communicate in a considerate and reassuring manner."
)
DEFAULT_WORKFLOW_ID = "wf_68eb7f8508dc81909a25f60b95ee0cba0410232f0e072ed7"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_MODEL = "gpt-5-nano"


class WorkflowInput(BaseModel):
    input_as_text: str


@dataclass
class WorkflowRunOutput:
    text: str
    raw_result: Any
    new_items: List[Any]


class AgentWorkflowEngine:
    """Wrapper around the OpenAI Agents/Workflows SDK."""

    def __init__(
        self,
        model: str,
        base_instructions: str,
        workflow_id: Optional[str],
        reasoning_effort: str,
        logger: logging.Logger,
    ):
        if not AGENT_SDK_AVAILABLE:
            raise RuntimeError("OpenAI Agent SDK is not installed.")

        self.model = model
        self.logger = logger
        self.base_instructions = base_instructions
        self.workflow_id = workflow_id or DEFAULT_WORKFLOW_ID
        self.reasoning_effort = reasoning_effort or DEFAULT_REASONING_EFFORT
        self.web_search_tool = WebSearchTool(
            search_context_size="medium",
            user_location={"type": "approximate"},
        )

    async def run(
        self,
        question: str,
        dynamic_instructions: Optional[str],
        include_web_search: bool,
        trace_metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkflowRunOutput:
        """Execute the workflow for a single-turn question."""
        conversation_history: List[TResponseInputItem] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": WorkflowInput(input_as_text=question).input_as_text,
                    }
                ],
            }
        ]

        tools = [self.web_search_tool] if include_web_search else []
        model_settings_kwargs: Dict[str, Any] = {"store": True}
        if Reasoning:
            model_settings_kwargs["reasoning"] = Reasoning(
                effort=self.reasoning_effort
            )

        final_instructions = self.base_instructions
        if dynamic_instructions:
            final_instructions = f"{self.base_instructions}\n\n{dynamic_instructions}"

        agent = Agent(
            name="AI Assistant",
            instructions=final_instructions,
            model=self.model,
            tools=tools,
            model_settings=ModelSettings(**model_settings_kwargs),
        )

        metadata = trace_metadata or {}
        if self.workflow_id and "workflow_id" not in metadata:
            metadata["workflow_id"] = self.workflow_id

        try:
            with trace("AI Assistant Workflow"):
                result = await Runner.run(
                    agent,
                    input=conversation_history,
                    run_config=RunConfig(trace_metadata=metadata),
                )
        except Exception as exc:
            self.logger.error("OpenAI workflow run failed: %s", exc, exc_info=True)
            raise

        return WorkflowRunOutput(
            text=result.final_output_as(str),
            raw_result=result,
            new_items=list(getattr(result, "new_items", [])),
        )

    @property
    def supports_web_tool(self) -> bool:
        return self.web_search_tool is not None

    @staticmethod
    def detect_web_tool_usage(output: WorkflowRunOutput) -> bool:
        """Best-effort detection of web_search tool usage."""
        target_keywords = ("web_search", "web-search", "web search")

        for item in output.new_items:
            name = AgentWorkflowEngine._extract_tool_name(item)
            if any(keyword in name for keyword in target_keywords):
                return True

        raw = output.raw_result
        for attr in ("invocations", "tool_invocations", "steps"):
            entries = getattr(raw, attr, None)
            if not entries:
                continue
            for entry in entries:
                name = AgentWorkflowEngine._extract_tool_name(entry)
                if any(keyword in name for keyword in target_keywords):
                    return True
        return False

    @staticmethod
    def _extract_tool_name(item: Any) -> str:
        if not item:
            return ""
        if isinstance(item, dict):
            for key in ("tool_name", "name", "type"):
                value = item.get(key)
                if value:
                    return str(value).lower()
        else:
            for attr in ("tool_name", "name", "type"):
                value = getattr(item, attr, None)
                if value:
                    return str(value).lower()
        return ""


class AIAssistantService:
    """AI Assistant service with OpenAI workflow integration."""

    def __init__(self):
        self.model = settings.OPENAI_MODEL or DEFAULT_MODEL
        self.base_instructions = DEFAULT_AGENT_INSTRUCTIONS
        self.workflow_id = settings.OPENAI_WORKFLOW_ID or DEFAULT_WORKFLOW_ID
        self.reasoning_effort = DEFAULT_REASONING_EFFORT
        self.workflow_engine: Optional[AgentWorkflowEngine] = None

        if not settings.OPENAI_API_KEY:
            logger.warning(
                "OPENAI_API_KEY is not configured; AI assistant workflow is disabled."
            )
            return

        if AGENT_SDK_AVAILABLE:
            try:
                self.workflow_engine = AgentWorkflowEngine(
                    model=self.model,
                    base_instructions=self.base_instructions,
                    workflow_id=self.workflow_id,
                    reasoning_effort=self.reasoning_effort,
                    logger=logger,
                )
            except Exception as exc:
                logger.error(
                    "Failed to initialize OpenAI workflow agent: %s", exc, exc_info=True
                )
                self.workflow_engine = None
        else:
            logger.warning(
                "OpenAI Agent SDK not installed. Install the Agents SDK to enable AI assistant workflows."
            )

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
        Generate AI response using OpenAI Workflows with optional web search.

        Args:
            question: User's question
            user_context: Optional context about the user
            include_web_search: Whether to include web search results

        Returns:
            Formatted response for ElevenLabs voice consumption
        """
        try:
            if not self.workflow_engine:
                logger.warning("Workflow engine not available.")
                err = self._create_error_response(
                    "AI workflow is unavailable. Please verify the Agents SDK installation."
                )
                if conversation_id:
                    err["conversation_id"] = conversation_id
                return err

            needs_web = include_web_search and self._needs_web_search(question)
            use_web_tool = include_web_search and self.workflow_engine.supports_web_tool
            dynamic_instructions = self._create_system_prompt(
                user_context=user_context,
                include_web_search=use_web_tool,
                force_web=force_web,
                needs_web=needs_web,
            )

            trace_metadata: Dict[str, Any] = {
                "__trace_source__": "ai-assistant-service",
            }
            if conversation_id:
                trace_metadata["conversation_id"] = conversation_id

            workflow_output = await self.workflow_engine.run(
                question=question,
                dynamic_instructions=dynamic_instructions,
                include_web_search=use_web_tool,
                trace_metadata=trace_metadata,
            )

            ai_response = workflow_output.text
            web_search_used = (
                use_web_tool
                and AgentWorkflowEngine.detect_web_tool_usage(workflow_output)
            )
            web_results: List[Dict[str, Any]] = []

            # Format response for ElevenLabs voice consumption
            formatted_response = self._format_for_voice(
                ai_response, web_results, web_search_used=web_search_used
            )
            if conversation_id:
                formatted_response["conversation_id"] = conversation_id

            logger.info(
                f"AI response generated for question: {question[:50]}..."
            )
            return formatted_response

        except Exception as e:
            logger.error(f"AI response generation failed: {str(e)}")
            err = self._create_error_response(str(e))
            if conversation_id:
                err["conversation_id"] = conversation_id
            return err

    def _create_system_prompt(
        self,
        user_context: Optional[str],
        include_web_search: bool,
        force_web: bool,
        needs_web: bool,
    ) -> str:
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

        if force_web and include_web_search:
            prompt += "\n\nWhen answering, you MUST invoke the web_search tool to verify the latest information before responding."
        elif include_web_search:
            prompt += "\n\nWhen information may be time-sensitive or uncertain, you MAY use the web_search tool to verify before responding."

        if needs_web and not force_web and include_web_search:
            prompt += "\n\nThis particular question appears current or time-sensitive. Strongly consider running a web_search query before finalizing your answer."

        return prompt

    def _format_for_voice(
        self,
        ai_response: str,
        web_results: List[Dict[str, Any]],
        web_search_used: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """Format the response for ElevenLabs voice consumption."""

        # Clean up the response for voice synthesis
        voice_text = self._clean_for_voice(ai_response)
        web_flag = (
            len(web_results) > 0 if web_search_used is None else bool(web_search_used)
        )

        return {
            "response": voice_text,
            "original_response": ai_response,
            "web_search_used": web_flag,
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
