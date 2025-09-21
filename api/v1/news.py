from fastapi import APIRouter, HTTPException
import logging
from services.news_service import serpapi
from schemas.news import NewsResponse, NewsRequest

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()


# @router.get("/")
# async def get_top_news_get(
#     q: str,  # Direct search query for SerpAPI (required)
#     limit: int = 3
# ):
#     """
#     Get top news stories (GET version for easy testing).
    
#     Args:
#         q: Direct search query for SerpAPI (required)
#         limit: Number of stories to return (1-50)
        
#     Returns:
#         NewsResponse with filtered news stories
#     """
#     # Log incoming request
#     logger.info(f"📥 GET /api/v1/news/top - Incoming request: q='{q}', limit={limit}")
    
#     try:
#         # Validate limit
#         if limit < 1 or limit > 50:
#             logger.warning(f"❌ GET /api/v1/news/top - Invalid limit: {limit}")
#             raise HTTPException(
#                 status_code=400,
#                 detail="Limit must be between 1 and 50"
#             )
        
#         logger.info(f"🔍 GET /api/v1/news/top - Fetching stories with query: '{q}', limit={limit}")
        
#         # Always use direct query approach
#         logger.info(f"🎯 Using direct query: '{q}'")
        
#         stories = await serpapi.get_latest_news(
#             country=None,  # Let the query handle location
#             category=None,  # Let the query handle category
#             language="en",  # Default to English, agent can specify in query
#             size=limit,
#             q=q  # Direct query from agent
#         )
        
#         if not stories:
#             logger.warning(f"⚠️ GET /api/v1/news/top - No stories found for request: q='{q}', limit={limit}")
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
#             logger.info(f"📤 GET /api/v1/news/top - Response sent: success={response.success}, total_count={response.total_count}")
#             logger.info(f"📋 Empty response - no stories found for the requested criteria")
            
#             return response
        
#         logger.info(f"✅ GET /api/v1/news/top - Found {len(stories)} stories")
        
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
#         # logger.info(f"📤 GET /api/v1/news/ - Response sent: success={response.success}, total_count={response.total_count}")
#         # for i, story in enumerate(response.stories, 1):
#         logger.info(f"📰 Stories : {response.stories}")
        
#         return response
        
#     except HTTPException as e:
#         logger.error(f"❌ GET /api/v1/news/top - HTTP Exception: {e.status_code} - {e.detail}")
#         raise
#     except Exception as e:
#         logger.error(f"❌ GET /api/v1/news/top - Unexpected error: {str(e)}")
#         raise HTTPException(
#             status_code=500,
#             detail=f"Internal server error: {str(e)}"
#         )
    

@router.post("/", response_model=NewsResponse)
async def get_top_news(request: NewsRequest):
    """
    Get top news stories filtered for positive, senior-friendly content.
    
    Args:
        request: News request with locale, language, categories, and limit
        
    Returns:
        NewsResponse with filtered news stories
    """
    # Log incoming request
    logger.info(f"📥 POST NEWS FETCH - Incoming request: {request.model_dump()}")
    
    try:
        # Always use direct query approach
        limit = request.limit or 3
        
        # Validate limit
        if limit < 1 or limit > 50:
            logger.warning(f"❌ POST /api/v1/news/top - Invalid limit: {limit}")
            raise HTTPException(
                status_code=400,
                detail="Limit must be between 1 and 50"
            )
        
        logger.info(f"🔍 POST /api/v1/news/top - Fetching stories with query: '{request.q}', limit={limit}")
        
        # Always use direct query approach
        logger.info(f"🎯 Using direct query: '{request.q}'")
        
        stories = await serpapi.get_latest_news(
            country=None,  # Let the query handle location
            category=None,  # Let the query handle category
            language="en",  # Default to English, agent can specify in query
            size=limit,
            q=request.q  # Direct query from agent
        )
        
        if not stories:
            logger.warning(f"⚠️ POST /api/v1/news/top - No stories found for request: {request.model_dump()}")
            # Return successful response with empty stories instead of error
            response = NewsResponse(
                success=True,
                stories=[],
                total_count=0,
                language="en",
                locale=None,
                categories=None
            )
            
            # Log outgoing response
            logger.info(f"📤 POST /api/v1/news/top - Response sent: success={response.success}, total_count={response.total_count}")
            logger.info(f"📋 Empty response - no stories found for the requested criteria")
            
            return response
        
        logger.info(f"✅ POST /api/v1/news/top - Found {len(stories)} stories")
        
        # Format the response to match our expected format
        stories_data = []
        for story in stories:
            # Map SerpAPI fields to our expected format
            formatted_story = {
                "title": story.get("title", "No title"),
                "description": story.get("description", "No description available"),
                "source": story.get("source", "Unknown source"),
                "published_at": story.get("published_at", ""),
                "language": "en"
            }
            stories_data.append(formatted_story)
        
        response = NewsResponse(
            success=True,
            stories=stories_data,
            total_count=len(stories),
            language="en",
            locale=None,
            categories=None
        )
        
        # Log outgoing response with story details
        logger.info(f"📤 POST /api/v1/news/top - Response sent: success={response.success}, total_count={response.total_count}")
        for i, story in enumerate(response.stories, 1):
            logger.info(f"📰 Story {i}: {story['title']} | Source: {story['source']} | Published: {story['published_at']}")
        
        return response
        
    except HTTPException as e:
        logger.error(f"❌ POST /api/v1/news/top - HTTP Exception: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        logger.error(f"❌ POST /api/v1/news/top - Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
