from pydantic import BaseModel
from typing import Optional

class StandardSuccessResponse(BaseModel):
    success: bool = True
    message: str
    session_id: Optional[str] = None

class StandardErrorResponse(BaseModel):
    success: bool = False
    message: str
    detail: Optional[str] = None