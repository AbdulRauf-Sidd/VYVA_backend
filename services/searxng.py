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

    last_exc: Exception | None = None
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    settings.SEARXNG_URL,
                    params={"q": query, "format": "json", "region": "es-ES"}
                )
                response.raise_for_status()
                results = response.json().get("results", [])[:num_results]
                if not results:
                    continue
                _cache[query] = (results, time.time())
                return results
        except Exception as e:
            last_exc = e
            logger.warning(f"SearXNG attempt {attempt + 1}/3 failed: {type(e).__name__}: {e}")

    logger.error(f"SearXNG all retries exhausted: {last_exc}")
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


async def warm_up():
    """Fire a throwaway query on startup so SearXNG's connection pool is alive."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            await client.get(
                settings.SEARXNG_URL,
                params={"q": "health", "format": "json", "region": "es-ES"},
            )
        logger.info("SearXNG warm-up complete.")
    except Exception as e:
        logger.warning(f"SearXNG warm-up failed (will retry on first real query): {e}")