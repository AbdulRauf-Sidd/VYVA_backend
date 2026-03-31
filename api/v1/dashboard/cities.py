from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Tuple

router = APIRouter()

SAXONY_CITY_COORDS: dict[str, Tuple[float, float]] = {
    "Dresden": (51.0504, 13.7373),
    "Leipzig": (51.3397, 12.3731),
    "Chemnitz": (50.8278, 12.9214),
    "Zwickau": (50.7189, 12.4964),
    "Plauen": (50.4974, 12.1346),
    "Görlitz": (51.1529, 14.9877),
    "Bautzen": (51.1814, 14.4244),
    "Freiberg": (50.9119, 13.3428),
    "Pirna": (50.9617, 13.9389),
    "Meissen": (51.1634, 13.4737),
    "Meißen": (51.1634, 13.4737),
    "Radebeul": (51.1069, 13.6569),
    "Freital": (51.0082, 13.6486),
    "Riesa": (51.3065, 13.2928),
    "Döbeln": (51.1209, 13.1163),
    "Grimma": (51.2389, 12.7276),
    "Delitzsch": (51.5254, 12.3428),
    "Torgau": (51.5603, 12.9961),
    "Annaberg": (50.5799, 13.0021),
    "Hamburg": (50.5799, 13.0021),
    "Berlin": (50.5799, 13.0021),
    "Annaberg-Buchholz": (50.5799, 13.0021),
}


def get_city_coords(city: Optional[str]) -> Optional[Tuple[float, float]]:
    if not city:
        return None

    normalized = city.strip()

    # Exact match
    if normalized in SAXONY_CITY_COORDS:
        return SAXONY_CITY_COORDS[normalized]

    # Case-insensitive match
    lower = normalized.lower()
    for key, coords in SAXONY_CITY_COORDS.items():
        if key.lower() == lower:
            return coords

    return None


@router.get("/city-coords")
async def city_coords(city: Optional[str] = Query(None)):
    coords = get_city_coords(city)

    if not coords:
        raise HTTPException(status_code=404, detail="City not found")

    return {
        "city": city,
        "latitude": coords[0],
        "longitude": coords[1],
    }