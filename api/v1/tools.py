"""
Tools API endpoints for Hybrid v1.

Provides:
- POST /api/v1/tools/find-places
- POST /api/v1/tools/get-information
"""

from fastapi import APIRouter, HTTPException, status
from typing import List
import logging

from schemas.tools import (
    FindPlacesRequest,
    FindPlacesResponse,
    PlaceSummary,
    GetInformationRequest,
    GetInformationResponse,
    Source,
)
from services.google_places_service import google_places
from math import radians, cos, sin, asin, sqrt
from services.ai_assistant_service import ai_assistant_service


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/find-places", response_model=FindPlacesResponse)
async def find_places(req: FindPlacesRequest) -> FindPlacesResponse:
    try:
        # Require either coords or a location_text; otherwise signal needs_location
        has_coords = req.latitude is not None and req.longitude is not None
        if not has_coords and not req.location_text:
            return FindPlacesResponse(results=[], needs_location=True, message="Please provide a city or area.")

        # Prefer coordinates when provided
        location = None
        if has_coords:
            location = (req.latitude, req.longitude)

        results_raw = await google_places.text_search(
            query=req.query,
            location_text=req.location_text,
            location=location,
            radius_meters=req.radius_meters if location else None,
            max_results=req.result_limit,
        )

        # Map to schema and compute distance if coords provided
        results: List[PlaceSummary] = []
        for r in results_raw:
            item = PlaceSummary(**r)
            if has_coords and item.latitude is not None and item.longitude is not None:
                item.distance_meters = int(_haversine_meters(req.latitude, req.longitude, item.latitude, item.longitude))
            results.append(item)

        # Rank by proximity, contact readiness, open_now, rating
        def contact_score(x: PlaceSummary) -> int:
            return 1 if (x.phone and len(x.phone) > 0) else 0

        results.sort(
            key=lambda x: (
                x.distance_meters if (x.distance_meters is not None) else 10**9,
                -contact_score(x),
                0 if x.open_now else 1,
                -(x.rating or 0.0),
            )
        )

        return FindPlacesResponse(results=results[: req.result_limit], needs_location=False)
    except Exception as e:
        logger.error(f"find_places failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to search places")


@router.post("/get-information", response_model=GetInformationResponse)
async def get_information(req: GetInformationRequest) -> GetInformationResponse:
    try:
        ai = await ai_assistant_service.generate_response(
            question=req.question,
            user_context=(
                "You are a helpful assistant for seniors. Keep answers short and clear. Cite source names if web was used."
            ),
            include_web_search=True,
            force_web=bool(req.web),
        )

        sources: List[Source] = []
        if ai.get("web_search_used"):
            for r in ai.get("web_results", [])[:5]:
                name = r.get("title") or r.get("link") or "Source"
                sources.append(Source(name=name))

        return GetInformationResponse(
            answer=ai.get("response") or ai.get("original_response") or "",
            used_web=bool(ai.get("web_search_used")),
            sources=sources,
        )
    except Exception as e:
        logger.error(f"get_information failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to get information")


def _haversine_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute haversine distance in meters between two coords."""
    # convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 6371000  # meters
    return c * r


