from pydantic import BaseModel
from typing import List, Optional
from enum import Enum as PyEnum

class MessageTypeEnum(str, PyEnum):
    emergency_contact_alert = "emergency_contact_alert"

class SendWhatsappMessage(BaseModel):
    user_id: int
    message: Optional[str]  
    message_type: MessageTypeEnum


class TwilioPersonalizationRequest(BaseModel):
    caller_id: str
    conversation_id: str
