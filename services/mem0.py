from mem0 import MemoryClient
from core.config import settings

# client = MemoryClient(api_key=settings.MEM0_API_KEY)

_client: MemoryClient | None = None

def get_mem0_client() -> MemoryClient:
    global _client
    if _client is None:
        _client = MemoryClient(api_key=settings.MEM0_API_KEY)
    return _client

async def add_memory(user_id: int, content: str) -> dict:
    client = get_mem0_client()
    client.add(content, str(user_id))
    return {"message": "Memory added successfully"}

async def add_conversation(user_id: int, conversation: list[dict]) -> dict:
    client = get_mem0_client()
    print('convo', conversation)
    client.add(conversation, user_id=str(user_id))
    return {"message": "Conversation added successfully"}

async def get_memories(user_id: int):
    client = get_mem0_client()
    result = client.get_all(
        filters={
            "user_id": str(user_id)
        }
    )
    results = result.get("results", [])
    memories = []
    for item in results:
        memories.append({
            "memory": item.get("memory"),
            "created_at": item.get("created_at").split("T")[0],
            # 'day of the week': item.get("day_of_the_week"),
        })
    return memories

    