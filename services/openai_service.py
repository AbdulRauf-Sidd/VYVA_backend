import json
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from core.database import SessionLocal
from models.brain_coach import BrainCoachResponses
from models.eleven_labs_sessions import ElevenLabsSessions
from models.medication import Medication, MedicationLog
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

    def get_medication_log_context(
        self,
        user_id: int,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        with SessionLocal() as db:
            stmt = (
                select(MedicationLog, Medication.name)
                .join(Medication, MedicationLog.medication_id == Medication.id)
                .where(MedicationLog.user_id == user_id)
                .order_by(desc(MedicationLog.created_at))
                .limit(limit)
            )
            result = db.execute(stmt)
            rows = result.all()
            return [
                {
                    "medication_name": name,
                    "status": log.status,
                    "taken_at": log.taken_at.isoformat() if log.taken_at else None,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log, name in rows
            ]

    def compute_med_streak(self, medication_logs: List[Dict[str, Any]]) -> int:
        streak = 0
        for log in medication_logs:
            if log.get("status") == "taken":
                streak += 1
            else:
                break
        return streak

    def get_brain_coach_session_context(
        self,
        user_id: int,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        with SessionLocal() as db:
            result = db.execute(
                select(BrainCoachResponses)
                .where(BrainCoachResponses.user_id == user_id)
                .options(selectinload(BrainCoachResponses.question))
                .order_by(BrainCoachResponses.created.asc())
            )
            responses = result.scalars().all()

        if not responses:
            return []

        sessions: Dict[str, list] = defaultdict(list)
        for r in responses:
            sessions[r.session_id].append(r)

        session_summaries = []
        for session_id, items in sessions.items():
            total_score = sum(r.score for r in items)
            max_score = sum((r.question.max_score or 1) for r in items)
            percent = round((total_score / max_score) * 100) if max_score else 0
            created_at = min((r.created for r in items if r.created), default=None)
            session_summaries.append({
                "session_id": session_id,
                "total_score": total_score,
                "max_score": max_score,
                "percent": percent,
                "question_count": len(items),
                "created": created_at.isoformat() if created_at else None,
            })

        session_summaries.sort(key=lambda x: x["created"] or "")
        return session_summaries[-limit:]

    def compute_brain_coach_trend(self, sessions: List[Dict[str, Any]]) -> str:
        percents = [s["percent"] for s in sessions]
        if len(percents) < 2:
            return "insufficient_data"
        delta = percents[-1] - percents[-2]
        if delta > 1:
            return "improving"
        elif delta < -1:
            return "declining"
        return "stable"

    async def generate_med_reminder_call_plan(
        self,
        db: AsyncSession,
        context: CallPlanContext,
    ) -> Dict[str, Any]:
        prompt_config = await self.get_prompt(
            db=db,
            prompt_type=PromptTypeEnum.medication_reminder_plan.value,
            organization_id=None,
            organization_agent_id=None,
            agent_type=None,
        )

        medication_logs = self.get_medication_log_context(user_id=context.user.id)
        recent_sessions = await self.get_recent_session_context(
            db=db,
            user_id=context.user.id,
            agent_type=None,
            limit=5,
        )
        memories = await self.get_user_memories(context.user.id)
        med_streak = self.compute_med_streak(medication_logs)

        from scripts.utils import get_zoneinfo_safe
        user_tz = get_zoneinfo_safe(context.user.timezone)
        local_time = datetime.now(timezone.utc).astimezone(user_tz).strftime("%Y-%m-%d %H:%M %Z")

        if not prompt_config:
            raise RuntimeError("No medication_reminder_plan prompt found in database.")
        system_prompt = prompt_config.prompt
        if "json" not in system_prompt.lower():
            system_prompt = f"{system_prompt}\n\nReturn only a valid JSON object."
        model = prompt_config.model if prompt_config.model else self.model

        user_payload = {
            "call_type": context.agent_type,
            "user": self.serialize_user(context.user),
            "local_time": local_time,
            "medication_logs": medication_logs,
            "med_streak": med_streak,
            "memories": memories,
            "recent_sessions": recent_sessions,
            "output_contract": {
                "call_plan": "private instructions for today's medication reminder call, one natural paragraph",
                "opening_line_direction": "how to open the call after greeting, as direction not script",
                "last_med_status": "neutral phrase about most recent adherence, empty string if none",
                "med_streak": "short encouraging phrase about streak, empty string if none",
                "health_tip": "one short general wellness tip based on health conditions, not medical advice",
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
            raise RuntimeError("OpenAI returned an empty med reminder call plan.")

        plan = json.loads(content)
        plan["dynamic_variable"] = self.format_med_reminder_plan(plan)
        return plan

    def format_med_reminder_plan(self, plan: Dict[str, Any]) -> str:
        compact = {
            "call_plan": plan.get("call_plan"),
            "opening_line_direction": plan.get("opening_line_direction"),
            "last_med_status": plan.get("last_med_status"),
            "med_streak": plan.get("med_streak"),
            "health_tip": plan.get("health_tip"),
        }
        return json.dumps(compact, ensure_ascii=False)

    async def generate_brain_coach_call_plan(
        self,
        db: AsyncSession,
        context: CallPlanContext,
    ) -> Dict[str, Any]:
        prompt_config = await self.get_prompt(
            db=db,
            prompt_type=PromptTypeEnum.brain_coach_plan.value,
            organization_id=None,
            organization_agent_id=None,
            agent_type=None,
        )

        brain_coach_sessions = self.get_brain_coach_session_context(user_id=context.user.id)
        recent_sessions = await self.get_recent_session_context(
            db=db,
            user_id=context.user.id,
            agent_type=None,
            limit=5,
        )
        memories = await self.get_user_memories(context.user.id)
        trend = self.compute_brain_coach_trend(brain_coach_sessions)
        last_session = brain_coach_sessions[-1] if brain_coach_sessions else None

        if not prompt_config:
            raise RuntimeError("No brain_coach_plan prompt found in database.")
        system_prompt = prompt_config.prompt
        if "json" not in system_prompt.lower():
            system_prompt = f"{system_prompt}\n\nReturn only a valid JSON object."
        model = prompt_config.model if prompt_config.model else self.model

        user_payload = {
            "call_type": context.agent_type,
            "user": self.serialize_user(context.user),
            "brain_coach_sessions": brain_coach_sessions,
            "last_session": last_session,
            "trend_direction": trend,
            "memories": memories,
            "recent_sessions": recent_sessions,
            "output_contract": {
                "call_plan": "private instructions for today's brain coach call, one natural paragraph",
                "opening_line_direction": "how to open the call after greeting, as direction not script",
                "suggested_activity": "cognitive activity recommended for today based on session history and trend",
                "last_session_score": "neutral phrase about last session performance, empty string if no history",
                "session_streak": "gentle encouragement phrase about current streak, empty string if none",
                "cognitive_health_tip": "short evidence-based motivation for daily thinking exercises",
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
            raise RuntimeError("OpenAI returned an empty brain coach call plan.")

        plan = json.loads(content)
        plan["dynamic_variable"] = self.format_brain_coach_plan(plan)
        return plan

    def format_brain_coach_plan(self, plan: Dict[str, Any]) -> str:
        compact = {
            "call_plan": plan.get("call_plan"),
            "opening_line_direction": plan.get("opening_line_direction"),
            "suggested_activity": plan.get("suggested_activity"),
            "last_session_score": plan.get("last_session_score"),
            "session_streak": plan.get("session_streak"),
            "cognitive_health_tip": plan.get("cognitive_health_tip"),
        }
        return json.dumps(compact, ensure_ascii=False)


openai_service = OpenAIService()
