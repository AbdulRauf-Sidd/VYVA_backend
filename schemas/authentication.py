from pydantic import BaseModel

class PhoneRequest(BaseModel):
    phone: str

class VerifyOtpRequest(BaseModel):
    session_id: str
    otp: str