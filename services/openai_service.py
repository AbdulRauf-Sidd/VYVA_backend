import asyncio
import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session, selectinload

from core.config import settings
from core.database import SessionLocal
from models.brain_coach import BrainCoachResponses
from models.eleven_labs_sessions import ElevenLabsSessions
from models.medication import Medication, MedicationLog
from models.organization import OrganizationAgents
from models.prompt import Prompt, PromptTypeEnum, UserConversationPlan
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
    prompt_type: str
    required_task: Optional[str] = None
    recent_plans: Optional[List[Dict[str, Any]]] = None
    medication_logs: Optional[List[Dict[str, Any]]] = None
    brain_coach_sessions: Optional[List[Dict[str, Any]]] = None
    memories: Optional[List[Dict[str, Any]]] = None


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
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("OpenAI SDK is not installed.") from exc
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY)
        return self._client

    # ── DB helpers (all sync, receive an open Session) ─────────────────────────

    def get_prompt(
        self,
        db: Session,
        prompt_type: str,
        organization_id: Optional[int],
        organization_agent_id: Optional[int],
        agent_type: Optional[str],
    ) -> Optional[Prompt]:
        stmt = (
            select(Prompt)
            .where(Prompt.is_active.is_(True))
            .where(Prompt.prompt_type == prompt_type)
            .where(or_(Prompt.organization_id == organization_id, Prompt.organization_id.is_(None)))
            .where(or_(Prompt.organization_agent_id == organization_agent_id, Prompt.organization_agent_id.is_(None)))
            .where(or_(Prompt.agent_type == agent_type, Prompt.agent_type.is_(None)))
        )
        prompts = db.execute(stmt).scalars().all()
        if not prompts:
            return None

        def score(p: Prompt) -> int:
            return sum([
                4 if p.organization_agent_id == organization_agent_id else 0,
                2 if p.organization_id == organization_id else 0,
                1 if p.agent_type == agent_type else 0,
            ])

        return sorted(prompts, key=score, reverse=True)[0]

    def save_plan(self, db: Session, user_id: int, plan_type: str, plan: Dict[str, Any]) -> None:
        db.add(UserConversationPlan(
            user_id=user_id,
            plan_type=plan_type,
            plan=plan,
            dynamic_variable=plan.get("dynamic_variable"),
        ))
        db.commit()
        logger.info("Saved conversation plan for user %s type %s", user_id, plan_type)

    # ── Pure helpers ────────────────────────────────────────────────────────────

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

    def compute_med_streak(self, medication_logs: List[Dict[str, Any]]) -> int:
        streak = 0
        for log in medication_logs:
            if log.get("status") == "taken":
                streak += 1
            else:
                break
        return streak

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

    def format_plan_for_agent(self, plan: Dict[str, Any]) -> str:
        return json.dumps({
            "call_plan": plan.get("call_plan"),
            "opening_line_direction": plan.get("opening_line_direction"),
            "suggested_topic": plan.get("suggested_topic"),
            "mood_guidance": plan.get("mood_guidance"),
            "watch_for": plan.get("watch_for"),
        }, ensure_ascii=False)

    def format_med_reminder_plan(self, plan: Dict[str, Any]) -> str:
        return json.dumps({
            "call_plan": plan.get("call_plan"),
            "opening_line_direction": plan.get("opening_line_direction"),
            "last_med_status": plan.get("last_med_status"),
            "med_streak": plan.get("med_streak"),
            "health_tip": plan.get("health_tip"),
        }, ensure_ascii=False)

    def format_brain_coach_plan(self, plan: Dict[str, Any]) -> str:
        return json.dumps({
            "call_plan": plan.get("call_plan"),
            "opening_line_direction": plan.get("opening_line_direction"),
            "suggested_activity": plan.get("suggested_activity"),
            "last_session_score": plan.get("last_session_score"),
            "session_streak": plan.get("session_streak"),
            "cognitive_health_tip": plan.get("cognitive_health_tip"),
        }, ensure_ascii=False)

    # ── Plan generators (sync, self-managed session) ────────────────────────────

    def generate_call_plan(self, db, context: CallPlanContext) -> Dict[str, Any]:
        from scripts.utils import get_zoneinfo_safe

        prompt_config = self.get_prompt(
            db, PromptTypeEnum.conversation_plan.value, None, None, context.agent_type
        )
        memories = context.memories
        recent_plans = context.recent_plans

        if not prompt_config:
            logger.info("No prompt config found for agent_type %s. Using default.", context.agent_type)
        
        system_prompt = prompt_config.prompt
        user_tz = get_zoneinfo_safe(context.user.timezone)
        local_time = datetime.now(timezone.utc).astimezone(user_tz).strftime("%Y-%m-%d %H:%M %Z")
        
        if "json" not in system_prompt.lower():
            system_prompt += "\n\nReturn only a valid JSON object."
        
        model = (prompt_config.model if prompt_config and prompt_config.model else self.model)
        user_payload = {
            "call_type": context.agent_type,
            "required_task": context.required_task,
            "user": self.serialize_user(context.user),
            "local_time": local_time,
            "memories": memories,
            "recent_plans": recent_plans,
            "output_contract": {
                "call_plan": "flowing instructions to VYVA, under 200 words",
                "opening_line_direction": "how VYVA should open, as a direction rather than a script",
                "suggested_topic": "main conversation thread for this call",
                "mood_guidance": "emotional register VYVA should hold",
                "watch_for": "one thing VYVA should be emotionally sensitive to",
            },
            "response_format": "Return only valid JSON matching the output_contract. Do not repeat topics or suggestions from recent_plans.",
        }
        completion = self._get_client().chat.completions.create(
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
        self.save_plan(db, context.user.id, PromptTypeEnum.conversation_plan.value, plan)
        return plan

    def generate_med_reminder_call_plan(self, db: Session, context: CallPlanContext) -> Dict[str, Any]:
        from scripts.utils import get_zoneinfo_safe

        prompt_config = self.get_prompt(
            db, PromptTypeEnum.medication_reminder_plan.value, None, None, None
        )
        if not prompt_config:
            raise RuntimeError("No medication_reminder_plan prompt found in database.")
        medication_logs = context.medication_logs
        recent_plans = context.recent_plans
        memories = context.memories
        med_streak = self.compute_med_streak(medication_logs)
        
        user_tz = get_zoneinfo_safe(context.user.timezone)
        local_time = datetime.now(timezone.utc).astimezone(user_tz).strftime("%Y-%m-%d %H:%M %Z")
        system_prompt = prompt_config.prompt

        if "json" not in system_prompt.lower():
            system_prompt += "\n\nReturn only a valid JSON object."
        model = prompt_config.model if prompt_config.model else self.model

        user_payload = {
            "call_type": context.agent_type,
            "user": self.serialize_user(context.user),
            "local_time": local_time,
            "medication_logs": medication_logs,
            "med_streak": med_streak,
            "memories": memories,
            "recent_plans": recent_plans,
            "output_contract": {
                "call_plan": "private instructions for today's medication reminder call, one natural paragraph",
                "opening_line_direction": "how to open the call after greeting, as direction not script",
                "last_med_status": "neutral phrase about most recent adherence, empty string if none",
                "med_streak": "short encouraging phrase about streak, empty string if none",
                "health_tip": "one short general wellness tip based on health conditions, not medical advice",
            },
            "response_format": "Return only valid JSON matching the output_contract. Do not repeat health tips or opening approaches from recent_plans.",
        }
        completion = self._get_client().chat.completions.create(
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
        self.save_plan(db, context.user.id, PromptTypeEnum.medication_reminder_plan.value, plan)
        
        return plan

    def generate_brain_coach_call_plan(self, db, context: CallPlanContext) -> Dict[str, Any]:
        from scripts.utils import get_zoneinfo_safe
        
        prompt_config = self.get_prompt(
            db, PromptTypeEnum.brain_coach_plan.value, None, None, None
        )
        if not prompt_config:
            raise RuntimeError("No brain_coach_plan prompt found in database.")
        brain_coach_sessions = context.brain_coach_sessions
        recent_plans = context.recent_plans
        memories = context.memories
        trend = self.compute_brain_coach_trend(brain_coach_sessions)
        last_session = brain_coach_sessions[-1] if brain_coach_sessions else None
        user_tz = get_zoneinfo_safe(context.user.timezone)
        local_time = datetime.now(timezone.utc).astimezone(user_tz).strftime("%Y-%m-%d %H:%M %Z")
        
        system_prompt = prompt_config.prompt
        if "json" not in system_prompt.lower():
            system_prompt += "\n\nReturn only a valid JSON object."

        model = prompt_config.model if prompt_config.model else self.model
        user_payload = {
            "call_type": context.agent_type,
            "user": self.serialize_user(context.user),
            "local_time": local_time,
            "brain_coach_sessions": brain_coach_sessions,
            "last_session": last_session,
            "trend_direction": trend,
            "memories": memories,
            "recent_plans": recent_plans,
            "output_contract": {
                "call_plan": "private instructions for today's brain coach call, one natural paragraph",
                "opening_line_direction": "how to open the call after greeting, as direction not script",
                "suggested_activity": "cognitive activity recommended for today based on session history and trend",
                "last_session_score": "neutral phrase about last session performance, empty string if no history",
                "session_streak": "gentle encouragement phrase about current streak, empty string if none",
                "cognitive_health_tip": "short evidence-based motivation for daily thinking exercises",
            },
            "response_format": "Return only valid JSON matching the output_contract. Do not repeat suggested activities or topics from recent_plans.",
        }
        completion = self._get_client().chat.completions.create(
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
        self.save_plan(db, context.user.id, PromptTypeEnum.brain_coach_plan.value, plan)
        return plan


openai_service = OpenAIService()
