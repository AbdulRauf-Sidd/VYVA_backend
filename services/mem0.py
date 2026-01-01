from mem0 import MemoryClient
from core.config import settings

client = MemoryClient(api_key=settings.MEM0_API_KEY)


async def add_memory(user_id: int, content: str) -> dict:
    client.add(content, str(user_id))

async def add_conversation(user_id: int, conversation: list[dict]) -> dict:
    client.add(conversation, user_id=str(user_id))
