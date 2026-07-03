from fastapi import APIRouter, HTTPException
import logging
from services.news_service import serpapi
from schemas.news import NewsResponse, NewsRequest
from core.config import settings
from typing import List, Dict
import httpx

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()



# -------------------------------------------------------------------
# Topic mapping
# -------------------------------------------------------------------

TOPIC_TO_CATEGORY = {
    "sports": "sports",
    "culture": "entertainment",
    "weather": "general",
    "business": "business",
    "general": "general",
    "latest": "general",
    "noticias": "general",
    "": "general",
}


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------

def get_location_params(location: str) -> Dict[str, str]:
    loc = (location or "Zamora").strip()
    lower = loc.lower()
    country = "es"
    keyword = "" if lower in ("spain", "españa") else loc
    return {"country": country, "keyword": keyword}


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@router.post("/", response_model=NewsResponse)
async def vyva_news(req: NewsRequest):
    if not req.location:
        raise HTTPException(
            status_code=400,
            detail={
                "ok": False,
                "error": "location is required",
                "message": "Please provide a location (e.g. Zamora, Madrid, Spain).",
            },
        )

    # limit clamp
    limit_num = min(max(int(req.limit or 5), 1), 25)

    category = TOPIC_TO_CATEGORY.get(
        (req.topic or "general").lower(),
        "general",
    )

    loc_params = get_location_params(req.location)
    country = loc_params["country"]
    keyword = loc_params["keyword"]

    keywords_param = " ".join(
        [k for k in [keyword, req.keywords] if k]
    ).strip()

    # ----------------------------------------------------------------
    # No API key
    # ----------------------------------------------------------------
    if not settings.MEDIASTACK_ACCESS_KEY:
        return {
            "ok": True,
            "location": req.location,
            "topic": category,
            "count": 0,
            "articles": [],
            "summary": "",
        }

    # ----------------------------------------------------------------
    # Call MediaStack
    # ----------------------------------------------------------------
    params = {
        "access_key": settings.MEDIASTACK_ACCESS_KEY,
        "countries": country,
        "categories": category,
        "limit": str(limit_num),
    }

    if keywords_param:
        params["keywords"] = keywords_param

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            api_res = await client.get("https://api.mediastack.com/v1/news", params=params)
            data = api_res.json()
    except Exception as e:
        print("Webhook error:", e)
        raise HTTPException(
            status_code=500,
            detail={
                "ok": False,
                "error": "server_error",
                "message": "Something went wrong fetching the news.",
            },
        )

    # ----------------------------------------------------------------
    # MediaStack error
    # ----------------------------------------------------------------
    if isinstance(data, dict) and data.get("error"):
        raise HTTPException(
            status_code=502,
            detail={
                "ok": False,
                "error": data["error"].get("code", "mediastack_error"),
                "message": data["error"].get(
                    "message", "Could not fetch news."
                ),
            },
        )

    raw = data.get("data", [])

    articles = [
        {
            "title": a.get("title", ""),
            "description": a.get("description") or "",
            "source": a.get("source") or "",
            "url": a.get("url") or "",
            "publishedAt": a.get("published_at") or "",
        }
        for a in raw
        if a.get("title")
    ][:limit_num]

    summary = " ".join(
        f"{a['title']}. {(a['description'] or '')[:120]}"
        for a in articles
    )

    return {
        "ok": True,
        "location": req.location,
        "topic": category,
        "count": len(articles),
        "articles": articles,
        "summary": summary,
    }
    