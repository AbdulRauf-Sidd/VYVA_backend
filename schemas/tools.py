from typing import List, Optional
from pydantic import BaseModel, Field


class FindPlacesRequest(BaseModel):
    query: str = Field(..., description="What to find, e.g., 'family doctor', '24-hour pharmacy'")
    location_text: Optional[str] = Field(None, description="City/area/ZIP if provided by the user")
    latitude: Optional[float] = Field(None, description="User latitude if available")
    longitude: Optional[float] = Field(None, description="User longitude if available")
    result_limit: int = Field(5, ge=1, le=10, description="Max results to return")
    with_details: bool = Field(False, description="If true, fetch place details where possible")
    radius_meters: int = Field(3000, ge=100, le=50000, description="Search radius in meters if coordinates provided")


class PlaceSummary(BaseModel):
    place_id: Optional[str] = None
    name: Optional[str] = None
    category: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    reviews: Optional[int] = None
    open_now: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    price_level: Optional[str] = None
    distance_meters: Optional[int] = None


class FindPlacesResponse(BaseModel):
    results: List[PlaceSummary] = Field(default_factory=list)
    needs_location: bool = False
    message: Optional[str] = None


class Source(BaseModel):
    name: str
    url: Optional[str] = None


class GetInformationRequest(BaseModel):
    question: str
    web: bool = Field(False, description="Set true to allow web lookup")
    sources_preferred: Optional[List[str]] = None


class GetInformationResponse(BaseModel):
    answer: str
    used_web: bool = False
    sources: List[Source] = Field(default_factory=list)

