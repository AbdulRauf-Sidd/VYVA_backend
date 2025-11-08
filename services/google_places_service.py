import httpx
from typing import Any, Dict, List, Optional, Tuple

from core.config import settings
from core.logging import get_logger


logger = get_logger(__name__)


class GooglePlacesService:
    """Thin wrapper around Google Places API v1 for text search and details."""

    def __init__(self) -> None:
        self.api_key = settings.GOOGLE_PLACES_API_KEY
        self.base_url = settings.GOOGLE_PLACES_BASE_URL.rstrip("/")
        if not self.api_key:
            logger.warning("GOOGLE_PLACES_API_KEY not configured; Places lookups will be disabled")

    def _is_enabled(self) -> bool:
        return bool(self.api_key)

    async def text_search(
        self,
        query: str,
        location_text: Optional[str] = None,
        location: Optional[Tuple[float, float]] = None,
        radius_meters: Optional[int] = None,
        max_results: int = 5,
    ) -> List[Dict[str, Any]]:
        if not self._is_enabled():
            return []

        url = f"{self.base_url}/places:searchText"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            # Field mask keeps payload small and includes needed fields
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,"
                "places.location,places.rating,places.userRatingCount,"
                "places.nationalPhoneNumber,places.websiteUri,places.priceLevel,"
                "places.currentOpeningHours.openNow,places.types"
            ),
            "Content-Type": "application/json",
        }
        # If only a textual location is available, bias results by including it in the text query
        text_query = query
        if location_text:
            text_query = f"{query} in {location_text}"
        body: Dict[str, Any] = {"textQuery": text_query}
        if location and radius_meters:
            lat, lng = location
            body["locationBias"] = {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": radius_meters,
                }
            }

        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.post(url, headers=headers, json=body)
                resp.raise_for_status()
                data = resp.json()
                results = data.get("places", [])[:max_results]
                return [self._map_place_summary_v1(r) for r in results]
        except Exception as e:
            logger.error(f"Google Places v1 text search failed: {str(e)}")
            return []

    async def place_details(self, place_id: str) -> Optional[Dict[str, Any]]:
        if not self._is_enabled():
            return None
        url = f"{self.base_url}/places/{place_id}"
        headers = {
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": (
                "id,displayName,formattedAddress,location,rating,userRatingCount,"
                "currentOpeningHours,regularOpeningHours,nationalPhoneNumber,websiteUri,"
                "priceLevel,types,accessibilityOptions"
            ),
        }
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                resp = await client.get(url, headers=headers)
                resp.raise_for_status()
                result = resp.json()
                return self._map_place_details_v1(result)
        except Exception as e:
            logger.error(f"Google Places v1 details failed: {str(e)}")
            return None

    def _map_place_summary_v1(self, r: Dict[str, Any]) -> Dict[str, Any]:
        loc = (r.get("location") or {})
        types = r.get("types") or []
        category = types[0].replace("_", " ").title() if types else None
        open_now = None
        try:
            open_now = (r.get("currentOpeningHours") or {}).get("openNow")
        except Exception:
            open_now = None
        display_name = (r.get("displayName") or {}).get("text")
        return {
            "place_id": r.get("id"),
            "name": display_name or r.get("name"),
            "address": r.get("formattedAddress"),
            "rating": r.get("rating"),
            "reviews": r.get("userRatingCount"),
            "location": loc,
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "price_level": r.get("priceLevel"),
            "category": category,
            "open_now": open_now,
            "phone": r.get("nationalPhoneNumber"),
            "website": r.get("websiteUri"),
        }

    def _map_place_details_v1(self, r: Dict[str, Any]) -> Dict[str, Any]:
        loc = r.get("location") or {}
        types = r.get("types") or []
        category = types[0].replace("_", " ").title() if types else None
        display_name = (r.get("displayName") or {}).get("text")
        open_now = None
        try:
            open_now = (r.get("currentOpeningHours") or {}).get("openNow")
        except Exception:
            open_now = None
        accessibility = (r.get("accessibilityOptions") or {})
        return {
            "place_id": r.get("id"),
            "name": display_name or r.get("name"),
            "address": r.get("formattedAddress"),
            "location": loc,
            "latitude": loc.get("latitude"),
            "longitude": loc.get("longitude"),
            "rating": r.get("rating"),
            "reviews": r.get("userRatingCount"),
            "opening_hours": (r.get("regularOpeningHours") or {}).get("weekdayDescriptions"),
            "open_now": open_now,
            "phone": r.get("nationalPhoneNumber"),
            "website": r.get("websiteUri"),
            "price_level": r.get("priceLevel"),
            "category": category,
            "accessibility": accessibility,
        }


google_places = GooglePlacesService()


