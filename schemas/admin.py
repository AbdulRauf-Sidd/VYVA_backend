from datetime import datetime
from pydantic import BaseModel


class ScheduleCallbackRequest(BaseModel):
    onboarding_user_id: int
    call_back_date_time: datetime
