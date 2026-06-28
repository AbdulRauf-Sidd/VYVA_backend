"""
Test script for web search via SearXNG.

Usage:
    python test_web_search.py "<query>" [num_results]

Examples:
    python test_web_search.py "latest diabetes research"
    python test_web_search.py "blood pressure medication" 3
"""

import asyncio
import sys

from services.searxng import web_search, searxng_search
from core.config import settings


async def main(query: str, num_results: int) -> None:
    print(f"SearXNG URL : {settings.SEARXNG_URL}")
    print(f"Query       : {query!r}")
    print(f"Num results : {num_results}")
    print("-" * 60)

    raw = await searxng_search(query, num_results)

    if not raw:
        print("No results returned. Check that SearXNG is running.")
        return

    print(f"Raw hits    : {len(raw)}\n")
    for i, r in enumerate(raw, 1):
        print(f"[{i}] {r.get('title', '—')}")
        print(f"    URL    : {r.get('url', '—')}")
        print(f"    Score  : {r.get('score', '—')}")
        print(f"    Snippet: {r.get('content', '—')[:120]}")
        print()

    print("=" * 60)
    print("Formatted output (as sent to LLM):\n")
    print(await web_search(query, num_results))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    q = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    asyncio.run(main(q, n))
