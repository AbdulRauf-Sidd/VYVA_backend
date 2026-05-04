import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from models.eleven_labs_sessions import ElevenLabsSessions
from models.organization import OrganizationAgents
from models.prompt import Prompt, PromptTypeEnum
from models.user import User
from services.mem0 import get_memories

logger = logging.getLogger(__name__)

DEFAULT_CALL_PLAN_PROMPT = """
You create warm, practical call plans for senior-care voice agents.
The caller is a friendly companion, not a survey robot.

Make the plan useful for one short phone call:
- Start with the required call purpose.
- Add one gentle personal touchpoint if the context supports it.
- Ask one or two natural follow-up questions.
- Avoid pretending to know facts that are not in the context.
- Avoid medical diagnosis. Escalate urgent symptoms or safety concerns.
- Keep it suitable for spoken conversation with an older adult.

Return only a valid JSON object.
"""


@dataclass
class CallPlanContext:
    user: User
    agent_type: str
    organization_agent_id: Optional[int] = None
    required_task: Optional[str] = None
    medication_context: Optional[Dict[str, Any]] = None


class OpenAIService:
    def __init__(self):
        self.model = settings.OPENAI_MODEL or "gpt-5-mini"
        self.max_tokens = settings.OPENAI_MAX_TOKENS or 1200
        self.temperature = 1
        self._client = None

    def _get_client(self):
        if not settings.OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not configured.")
        if self._client is None:
            try:
                from openai import AsyncOpenAI  # type: ignore
            except ImportError as exc:
                raise RuntimeError("OpenAI SDK is not installed.") from exc
            self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    async def generate_call_plan(
        self,
        db: AsyncSession,
        context: CallPlanContext,
    ) -> Dict[str, Any]:
        prompt_config = await self.get_prompt(
            db=db,
            prompt_type=PromptTypeEnum.conversation_plan.value,
            organization_id=None,
            organization_agent_id=None,
            agent_type=context.agent_type,
        )
        context_config = prompt_config.context_config if prompt_config and prompt_config.context_config else {}
        recent_sessions = await self.get_recent_session_context(
            db=db,
            user_id=context.user.id,
            agent_type=None,
            limit=context_config.get("max_recent_sessions", 5),
        )
        
        memories = await self.get_user_memories(context.user.id)
        if not prompt_config:
            logger.info("No prompt config found for agent_type %s. Using default.", context.agent_type)

        system_prompt = prompt_config.prompt if prompt_config else DEFAULT_CALL_PLAN_PROMPT
        if "json" not in system_prompt.lower():
            system_prompt = f"{system_prompt}\n\nReturn only a valid JSON object."
        model = prompt_config.model if prompt_config and prompt_config.model else self.model
        user_payload = {
            "call_type": context.agent_type,
            "required_task": context.required_task,
            "user": self.serialize_user(context.user),
            "memories": memories,
            "recent_sessions": recent_sessions,
            "output_contract": {
                "call_plan": "flowing instructions to VYVA, under 200 words",
                "opening_line_direction": "how VYVA should open, as a direction rather than a script",
                "suggested_topic": "main conversation thread for this call",
                "mood_guidance": "emotional register VYVA should hold",
                "watch_for": "one thing VYVA should be emotionally sensitive to",
            },
            "response_format": "Return only valid JSON matching the output_contract.",
        }

        completion = await self._get_client().chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload, default=str)},
            ],
            response_format={"type": "json_object"},
            max_completion_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise RuntimeError("OpenAI returned an empty call plan.")

        plan = json.loads(content)
        plan["dynamic_variable"] = self.format_plan_for_agent(plan)
        return plan

    async def get_prompt(
        self,
        db: AsyncSession,
        prompt_type: str,
        organization_id: Optional[int],
        organization_agent_id: Optional[int],
        agent_type: Optional[str],
    ) -> Optional[Prompt]:
        stmt = (
            select(Prompt)
            .where(Prompt.is_active.is_(True))
            .where(Prompt.prompt_type == prompt_type)
            .where(
                or_(
                    Prompt.organization_id == organization_id,
                    Prompt.organization_id.is_(None),
                )
            )
            .where(
                or_(
                    Prompt.organization_agent_id == organization_agent_id,
                    Prompt.organization_agent_id.is_(None),
                )
            )
            .where(
                or_(
                    Prompt.agent_type == agent_type,
                    Prompt.agent_type.is_(None),
                )
            )
        )
        result = await db.execute(stmt)
        prompts = result.scalars().all()
        if not prompts:
            return None

        def score(prompt: Prompt) -> int:
            return sum(
                [
                    4 if prompt.organization_agent_id == organization_agent_id else 0,
                    2 if prompt.organization_id == organization_id else 0,
                    1 if prompt.agent_type == agent_type else 0,
                ]
            )

        return sorted(prompts, key=score, reverse=True)[0]

    async def get_recent_session_context(
        self,
        db: AsyncSession,
        user_id: int,
        agent_type: Optional[str],
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        stmt = (
            select(ElevenLabsSessions)
            .where(ElevenLabsSessions.user_id == user_id)
            .order_by(desc(ElevenLabsSessions.created))
            .limit(limit)
        )
        if agent_type:
            stmt = stmt.where(ElevenLabsSessions.agent_type == agent_type)

        result = await db.execute(stmt)
        sessions = result.scalars().all()
        return [
            {
                "agent_type": session.agent_type,
                "duration": session.duration,
                "summary": session.summary,
                "transcription": session.transcription,
                "created": session.created,
            }
            for session in sessions
        ]

    async def get_user_memories(self, user_id: int) -> List[Dict[str, Any]]:
        try:
            return await get_memories(user_id)
        except Exception as exc:
            logger.warning("Unable to load mem0 memories for user %s: %s", user_id, exc)
            return []

    def serialize_user(self, user: User) -> Dict[str, Any]:
        return {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "age": user.age,
            "phone_number": user.phone_number,
            "timezone": user.timezone,
            "health_conditions": user.health_conditions,
            "mobility": user.mobility,
            "address": user.address,
            "city": user.city,
            "country": user.country,
            "preferred_reminder_channel": user.preferred_reminder_channel,
        }

    def format_plan_for_agent(self, plan: Dict[str, Any]) -> str:
        compact = {
            "call_plan": plan.get("call_plan"),
            "opening_line_direction": plan.get("opening_line_direction"),
            "suggested_topic": plan.get("suggested_topic"),
            "mood_guidance": plan.get("mood_guidance"),
            "watch_for": plan.get("watch_for"),
        }
        return json.dumps(compact, ensure_ascii=False)

    async def find_organization_agent(
        self,
        db: AsyncSession,
        organization_id: Optional[int],
        agent_type: str,
    ) -> Optional[OrganizationAgents]:
        if not organization_id:
            return None
        result = await db.execute(
            select(OrganizationAgents).where(
                OrganizationAgents.organization_id == organization_id,
                OrganizationAgents.agent_type == agent_type,
                OrganizationAgents.is_active.is_(True),
            )
        )
        return result.scalars().first()


openai_service = OpenAIService()
