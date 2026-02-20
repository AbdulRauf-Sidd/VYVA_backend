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

@router.post("/news", response_model=NewsResponse)
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
    

# @router.post("/", response_model=NewsResponse)
# async def get_top_news(request: NewsRequest):
#     """
#     Get top news stories filtered for positive, senior-friendly content.
    
#     Args:
#         request: News request with locale, language, categories, and limit
        
#     Returns:
#         NewsResponse with filtered news stories
#     """
#     # Log incoming request
#     logger.info(f"📥 POST NEWS FETCH - Incoming request: {request.model_dump()}")
    
#     try:
#         # Always use direct query approach
#         limit = request.limit or 3
        
#         # Validate limit
#         if limit < 1 or limit > 50:
#             logger.warning(f"❌ POST /api/v1/news/top - Invalid limit: {limit}")
#             raise HTTPException(
#                 status_code=400,
#                 detail="Limit must be between 1 and 50"
#             )
        
#         logger.info(f"🔍 POST /api/v1/news/top - Fetching stories with query: '{request.q}', limit={limit}")
        
#         # Always use direct query approach
#         logger.info(f"🎯 Using direct query: '{request.q}'")
        
#         stories = await serpapi.get_latest_news(
#             country=None,  # Let the query handle location
#             category=None,  # Let the query handle category
#             language="en",  # Default to English, agent can specify in query
#             size=limit,
#             q=request.q  # Direct query from agent
#         )
        
#         if not stories:
#             logger.warning(f"⚠️ POST /api/v1/news/top - No stories found for request: {request.model_dump()}")
#             # Return successful response with empty stories instead of error
#             response = NewsResponse(
#                 success=True,
#                 stories=[],
#                 total_count=0,
#                 language="en",
#                 locale=None,
#                 categories=None
#             )
            
#             # Log outgoing response
#             logger.info(f"📤 POST /api/v1/news/top - Response sent: success={response.success}, total_count={response.total_count}")
#             logger.info(f"📋 Empty response - no stories found for the requested criteria")
            
#             return response
        
#         logger.info(f"✅ POST /api/v1/news/top - Found {len(stories)} stories")
        
#         # Format the response to match our expected format
#         stories_data = []
#         for story in stories:
#             # Map SerpAPI fields to our expected format
#             formatted_story = {
#                 "title": story.get("title", "No title"),
#                 "description": story.get("description", "No description available"),
#                 "source": story.get("source", "Unknown source"),
#                 "published_at": story.get("published_at", ""),
#                 "language": "en"
#             }
#             stories_data.append(formatted_story)
        
#         response = NewsResponse(
#             success=True,
#             stories=stories_data,
#             total_count=len(stories),
#             language="en",
#             locale=None,
#             categories=None
#         )
        
#         # Log outgoing response with story details
#         logger.info(f"📤 POST /api/v1/news/top - Response sent: success={response.success}, total_count={response.total_count}")
#         for i, story in enumerate(response.stories, 1):
#             logger.info(f"📰 Story {i}: {story['title']} | Source: {story['source']} | Published: {story['published_at']}")
        
#         return response
        
#     except HTTPException as e:
#         logger.error(f"❌ POST /api/v1/news/top - HTTP Exception: {e.status_code} - {e.detail}")
#         raise
#     except Exception as e:
#         logger.error(f"❌ POST /api/v1/news/top - Unexpected error: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Internal server error: {str(e)}"
#         )
