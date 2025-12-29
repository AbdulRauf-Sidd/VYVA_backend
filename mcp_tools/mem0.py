from .mcp_instance import mcp
# from sqlalchemy import select
from typing import Optional
# from core.database import get_async_session
from pydantic import BaseModel
from models.user import User
from services.mem0 import add_conversation

class AddMemoryInput(BaseModel):
    conversation: list[dict]
    user_id: int

@mcp.tool(
    name="add_to_user_memory",
    description=(
        "Add a summarized, long-term memory about the user for future conversations.\n\n"

        "ONLY use this tool when the conversation contains stable, reusable information "
        "about the user that will meaningfully improve future interactions. Stored memories "
        "should be concise summaries, not raw transcripts.\n\n"

        "APPROPRIATE memories include:\n"
        "1. User identity and context: preferred name or nickname, language, time zone, "
        "approximate age group, living situation, or preferred communication channel.\n"
        "2. Routine and schedule: typical sleep/wake times, preferred reminder times, "
        "recurring habits or weekly activities.\n"
        "3. Conversation and companionship preferences: topics the user enjoys or avoids, "
        "preferred tone (humorous vs serious), verbosity, or interaction style.\n"
        "4. Cognitive and emotional profile: general mood trends, coping strategies that work "
        "well, preferred games or difficulty levels.\n"
        "5. Health and safety context (only summarized, day-to-day relevance): ongoing "
        "conditions, medication schedules, reminder preferences, or escalation rules—only "
        "when explicitly relevant and enabled.\n"
        "6. Care network: names and roles of close family, caregivers, or emergency contacts, "
        "plus notification preferences.\n"
        "7. Trusted services and logistics: preferred pharmacies, clinics, transport providers, "
        "or frequently visited locations for reminders or bookings.\n"
        "8. Interaction and UX preferences: known friction points, accessibility adjustments, "
        "explicit do’s and don’ts for agent behavior.\n\n"

        "DO NOT store:\n"
        "- Task-specific instructions, debugging steps, or one-off plans\n"
        "- Full dates of birth, national IDs, full addresses, payment details, passwords, or codes\n"
        "- Raw medical records, lab results, or detailed reports (store summaries only)\n"
        "- Continuous location data, raw audio, or sensor streams\n"
        "- Political opinions, intimate details, or sensitive traits unless explicitly requested\n"
        "- Trivial small talk, jokes, or short-lived emotional statements\n"
        "- Detailed profiles of third parties beyond name, role, and alert relevance\n\n"

        "When saving, summarize the relevant points in neutral language, focusing on patterns, "
        "preferences, or ongoing context that will remain useful over time."

        "Example input:\n"
        '{\n'
        '  "user_id": 123,\n'
        '  "conversation": [\n'
        '    {"role": "system", "content": "Do you have any health conditions we should be aware of?"},\n'
        '    {"role": "user", "content": "Yes, I have hypertension and mild arthritis."}\n'
        '  ]\n'
        '}\n'
    )
)
async def add_to_user_memory(input: AddMemoryInput) -> Optional[bool]:
    await add_conversation(input.user_id, input.conversation)
    return True