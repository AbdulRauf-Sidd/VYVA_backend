"""
Tools API endpoints for Hybrid v1.

Provides:
- POST /api/v1/tools/find-places
- POST /api/v1/tools/get-information
"""

from fastapi import APIRouter, HTTPException, status, Depends
from typing import List, Dict, Any
import logging
from urllib.parse import quote

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
from services.email_service import EmailService
from services.whatsapp_service import WhatsAppService
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from core.database import get_db
from models.user import User


logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/find-places", response_model=FindPlacesResponse)
async def find_places(req: FindPlacesRequest, db: AsyncSession = Depends(get_db)) -> FindPlacesResponse:
    try:
        logger.info(f"=====================> find-places called with request: {req}")
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

        results = results[: req.result_limit]

        # Resolve preferred channel and send places to user
        user_result = await db.execute(
            select(User).where(User.id == req.user_id)
        )
        user = user_result.scalar_one_or_none()
        if not user:
            raise HTTPException(
                status_code=404,
                detail=f"User not found for user_id: {req.user_id}"
            )

        preferred_channel = (user.preferred_communication_channel or "").strip().lower()
        if preferred_channel not in ["email", "whatsapp"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid preferred_communication_channel. Must be 'email' or 'whatsapp'."
            )

        recipient_email = (user.email or "").strip()
        phone_number = (user.phone_number or "").strip()

        send_status = "skipped"
        if preferred_channel == "email":
            if not recipient_email:
                raise HTTPException(
                    status_code=400,
                    detail="User email is required to send places via email."
                )
            send_status = await _send_places_email(
                recipient_email=recipient_email,
                query=req.query,
                results=results
            )
        elif preferred_channel == "whatsapp":
            if not phone_number:
                raise HTTPException(
                    status_code=400,
                    detail="User phone_number is required to send places via WhatsApp."
                )
            send_status = await _send_places_whatsapp(
                phone_number=phone_number,
                query=req.query,
                results=results
            )

        return FindPlacesResponse(
            results=results,
            needs_location=False,
            message=f"Places sent via {preferred_channel}: {send_status}"
        )
    except Exception as e:
        logger.error(f"find_places failed: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to search places")


@router.post("/get-information", response_model=GetInformationResponse)
async def get_information(req: GetInformationRequest) -> GetInformationResponse:
    try:
        logger.info(f"=====================> get-information called with request: {req}")
        ai = await ai_assistant_service.generate_response(
            question=req.question,
            user_context=(
                "You are a helpful assistant for seniors. Keep answers short and clear. Cite source names if web was used."
            ),
            include_web_search=True,
            force_web=True,
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


def _build_places_email_html(query: str, results: List[PlaceSummary]) -> str:
    items_html = ""
    for idx, item in enumerate(results, start=1):
        name = item.name or "N/A"
        rating = f"{item.rating:.1f}" if item.rating is not None else "N/A"
        address = item.address or "N/A"
        link = item.website or _build_maps_link(item)
        items_html += (
            f"<li><strong>{idx}. {name}</strong> — ⭐ {rating}<br>"
            f"{address}<br>"
            f"<a href=\"{link}\">{link}</a></li>"
        )

    return f"""
    <html>
      <body>
        <p>Hello!</p>
        <p>Here are your {query} options:</p>
        <ol>
          {items_html}
        </ol>
        <p>Reply with your choice and I will help.</p>
        <p>— VYVA Health</p>
      </body>
    </html>
    """


def _build_maps_link(item: PlaceSummary) -> str:
    if item.latitude is not None and item.longitude is not None:
        return f"https://www.google.com/maps/search/?api=1&query={item.latitude},{item.longitude}"
    query_parts = " ".join([p for p in [item.name, item.address] if p])
    if not query_parts:
        return "https://www.google.com/maps"
    return f"https://www.google.com/maps/search/?api=1&query={quote(query_parts)}"


def _format_place_value(value: Any) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.1f}"
    return str(value)


def _build_places_template_data(query: str, results: List[PlaceSummary]) -> Dict[str, str]:
    slots: Dict[str, str] = {}
    slots["1"] = _format_place_value(query)
    for idx in range(3):
        item = results[idx] if idx < len(results) else None
        name = _format_place_value(item.name if item else None)
        rating = _format_place_value(item.rating if item else None)
        address = _format_place_value(item.address if item else None)
        link = _format_place_value(item.website if item and item.website else _build_maps_link(item) if item else None)

        base = 2 + idx * 4
        slots[str(base)] = name
        slots[str(base + 1)] = rating
        slots[str(base + 2)] = address
        slots[str(base + 3)] = link
    slots["14"] = "Your VYVA Assistant"
    return slots


async def _send_places_email(
    recipient_email: str,
    query: str,
    results: List[PlaceSummary]
) -> str:
    try:
        email_service = EmailService()
        html_body = _build_places_email_html(query=query, results=results)
        await email_service.send_email_via_mailgun(
            to=[recipient_email],
            subject=f"Your {query} options",
            html=html_body
        )
        logger.info(f"Places email sent to {recipient_email}")
        return "email_sent"
    except Exception as e:
        logger.error(f"Failed to send places email to {recipient_email}: {str(e)}")
        return "email_failed"


async def _send_places_whatsapp(
    phone_number: str,
    query: str,
    results: List[PlaceSummary]
) -> str:
    try:
        whatsapp_service = WhatsAppService()
        template_data = _build_places_template_data(query=query, results=results)
        success = await whatsapp_service.send_reminder_message(
            to_phone=phone_number,
            template_data=template_data,
            template_id="HX4bcd81298ec36ad7f2f0fe4f80077921"
        )
        if success:
            logger.info(f"Places WhatsApp sent to {phone_number}")
            return "whatsapp_sent"
        logger.error(f"Failed to send places WhatsApp to {phone_number}")
        return "whatsapp_failed"
    except Exception as e:
        logger.error(f"Failed to send places WhatsApp: {str(e)}")
        return "whatsapp_failed"


