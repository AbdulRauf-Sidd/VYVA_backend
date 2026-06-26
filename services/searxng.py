import requests
from core.config import settings

def searxng_search(query: str, num_results: int = 5):
    """
    Calls SearXNG and returns raw JSON response.
    """
    try:
        response = requests.get(
            settings.SEARXNG_URL,
            params={
                "q": query,
                "format": "json"
            },
            timeout=5
        )

        response.raise_for_status()
        data = response.json()

        return data.get("results", [])[:num_results]

    except Exception as e:
        print(f"SearXNG error: {e}")
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

        formatted.append(
            f"{i}. {title}\n{url}\n{content}"
        )

    return "\n\n".join(formatted)

def web_search(query: str, num_results: int = 5):
    """
    Performs a web search using SearXNG and returns formatted results.
    """
    raw_results = searxng_search(query, num_results)
    return format_search_results(raw_results)