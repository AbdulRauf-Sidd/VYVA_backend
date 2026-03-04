from fastapi import APIRouter, Body, Query, HTTPException
from typing import Dict, Any, List, Optional
import httpx
import os
import logging
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

SERPAPI_API_KEY = settings.SERP_API_KEY


# NEWS HELPERS
def build_serpapi_news_query(location, topic, keywords):
    parts = [location if location and location.lower() != "spain" else "España"]

    if topic and isinstance(topic, str):
        t = topic.lower().strip()

        if t in ["sports", "sport"]:
            parts.append("deportes")
        elif t in ["culture", "entertainment", "arte", "cultura"]:
            parts.append("cultura")
        elif t in ["weather", "clima"]:
            parts.append("clima tiempo")
        elif t in ["business", "negocios", "economy"]:
            parts.append("economía negocios")

    if keywords:
        parts.append(keywords)

    return " ".join(parts)


def links_from_serpapi_news(data) -> List[Dict[str, Any]]:
    links = []
    news = data.get("news_results") or []

    for item in news:
        def add(title, source, date):
            if title:
                links.append({
                    "title": title,
                    "source": source or "",
                    "published_at": date,
                })

        top_source = (item.get("source") or {}).get("name", "")

        if item.get("link"):
            title = item.get("title") or (item.get("highlight") or {}).get("title")
            add(title, top_source, item.get("date") or item.get("iso_date"))

        for story in item.get("stories") or []:
            if story.get("link") and (story.get("title") or "").strip():
                add(
                    story.get("title"),
                    (story.get("source") or {}).get("name") or top_source,
                    story.get("date") or story.get("iso_date"),
                )

    return links


# WEATHER HELPERS

def weather_summary_from_serp(data, place):
    box = data.get("answer_box")

    if not box:
        first = (data.get("organic_results") or [{}])[0]
        if first.get("snippet"):
            return first["snippet"]
        return None

    type_ = box.get("type", "")

    if type_ in ["weather_result", "weather_year_round"]:
        temp = box.get("temperature")
        unit = box.get("unit", "°C")
        desc = box.get("weather") or box.get("current_weather")
        humidity = box.get("humidity")
        precipitation = box.get("precipitation")

        parts = []
        if temp:
            parts.append(f"{temp} {unit}")
        if desc:
            parts.append(desc)
        if humidity:
            parts.append(f"Humedad {humidity}")
        if precipitation:
            parts.append(f"Precipitación {precipitation}")

        return ". ".join(parts) if parts else box.get("title")

    if box.get("result"):
        return str(box["result"])

    return box.get("title")


async def handle_vyva_weather(location: Optional[str], user_location: Optional[str]):
    place = (location or "").strip() or (user_location or "").strip() or "Zamora"

    try:
        params = {
            "engine": "google",
            "q": f"tiempo {place} España",
            "gl": "es",
            "hl": "es",
            "api_key": settings.SERPAPI_API_KEY,
        }

        async with httpx.AsyncClient(timeout=30) as client:
            serp_res = await client.get("https://serpapi.com/search", params=params)
            data = serp_res.json()

        if data.get("error"):
            return {
                "success": False,
                "message": data["error"],
                "location": place,
            }

        summary = weather_summary_from_serp(data, place)
        answer_box = data.get("answer_box") or {}

        weather = {
            "location": place,
            "summary": summary or "No hay resumen del tiempo disponible.",
            "temperature": answer_box.get("temperature"),
            "unit": answer_box.get("unit"),
            "description": answer_box.get("weather"),
            "humidity": answer_box.get("humidity"),
            "precipitation": answer_box.get("precipitation"),
            "forecast": answer_box.get("forecast"),
        }

        return {
            "success": True,
            "message": "Weather fetched and sent to VYVA",
            "location": place,
            "weather": weather,
            "summary": weather["summary"],
        }

    except Exception as e:
        logger.exception("[vyva-weather] %s", e)
        return {
            "success": False,
            "message": str(e),
            "location": place,
        }


# ROUTES

@router.post("/vyva-news")
async def vyva_news(body: Dict[str, Any] = Body(...)):
    location = body.get("location")
    topic = body.get("topic")
    keywords = body.get("keywords")
    limit_param = body.get("limit")

    if not location:
        return {
            "success": False,
            "message": "Location is required",
            "location": location,
            "links": [],
        }

    limit = min(int(limit_param or 10), 25)

    if not settings.SERP_API_KEY:
        return {
            "success": False,
            "message": "News not configured; set SERPAPI_API_KEY.",
            "location": location,
            "links": [],
        }

    try:
        q = build_serpapi_news_query(location, topic, keywords)

        params = {
            "engine": "google_news",
            "api_key": SERPAPI_API_KEY,
            "q": q or "noticias España",
            "gl": "es",
            "hl": "es",
            "num": str(limit),
        }

        async with httpx.AsyncClient(timeout=30) as client:
            serp_res = await client.get("https://serpapi.com/search", params=params)
            serp_data = serp_res.json()

        if serp_data.get("error"):
            return {
                "success": False,
                "message": serp_data["error"],
                "location": location,
                "links": [],
            }

        links = links_from_serpapi_news(serp_data)[:limit]


        return {
            "success": True,
            "message": "News fetched",
            "location": location,
            "topic": topic or "general",
            "count": len(links),
            "links": links,
        }

    except Exception as e:
        logger.exception("[vyva-news] %s", e)
        return {
            "success": False,
            "message": str(e),
            "location": location,
            "links": [],
        }


@router.get("/vyva-weather")
async def vyva_weather_get(
    location: Optional[str] = Query(None),
    user_location: Optional[str] = Query(None),
):
    return await handle_vyva_weather(location, user_location)


@router.post("/vyva-weather")
async def vyva_weather_post(body: Dict[str, Any] = Body(...)):
    return await handle_vyva_weather(
        body.get("location"),
        body.get("user_location"),
    )
