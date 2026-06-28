import requests
from core.config import settings
from functools import lru_cache
import time
import httpx
import logging

logger = logging.getLogger(__name__)

_cache: dict[str, tuple[list, float]] = {}

async def searxng_search(query: str, num_results: int = 5):
    if query in _cache:
        results, ts = _cache[query]
        if time.time() - ts < 120:
            return results

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(
                settings.SEARXNG_URL,
                params={"q": query, "format": "json", "region": "es-ES"}
            )
            response.raise_for_status()
            results = response.json().get("results", [])[:num_results]
            _cache[query] = (results, time.time())
            return results
    except Exception as e:
        logger.error(f"SearXNG error: {e}")
        return []

def format_search_results(results):
    """
    Formats top search results into clean text for LLM / voice.
    """

    if not results:
        return "No search results found."

    formatted = []

    for i, r in enumerate(results[:5], start=1):
        title = r.get("title", "No title")
        url = r.get("url", "")
        content = r.get("content", "No description available")

        formatted.append({
            "title": title,
            "url": url,
            "content": content
        })

    return formatted

async def web_search(query: str, num_results: int = 5):
    """
    Performs a web search using SearXNG and returns formatted results.
    """
    raw_results = await searxng_search(query, num_results)
    return format_search_results(raw_results)