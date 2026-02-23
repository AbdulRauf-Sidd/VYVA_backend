from pydantic import BaseModel
from typing import Optional

class PhoneRequest(BaseModel):
    phone: str

class VerifyOtpRequest(BaseModel):
    session_id: str
    otp: str


class CaretakerProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone_number: Optional[str] = None