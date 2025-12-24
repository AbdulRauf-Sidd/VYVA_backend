from pydantic import BaseModel
from typing import Optional, Any

class StandardSuccessResponse(BaseModel):
    success: bool = True
    message: str
    data: Optional[Any] = None

class SessionCheckResponse(BaseModel):
    success: bool = True
    user_id: int
    first_name: Optional[str] = None

class SessionSuccessResponse(BaseModel):
    success: bool = True
    message: str
    session_id: Optional[str] = None

class StandardErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[str] = None