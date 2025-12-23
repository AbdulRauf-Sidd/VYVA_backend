from datetime import datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import Caretaker

TZ_MAP = {
    "cet": "Europe/Berlin",
    "est": "America/New_York",
    "utc": "UTC",
}

def date_time_to_utc(dt: datetime, tz_name: str | None = None) -> datetime:
    if dt.tzinfo is None:
        if tz_name:
            dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(ZoneInfo("UTC"))


def time_to_utc(preferred_time: datetime, tz_abbr: str) -> time:
    # local_time = datetime.strptime(preferred_time, "%H:%M").time()
    tz_name = TZ_MAP.get(tz_abbr.lower(), "UTC")
    today = date.today()
    local_dt = datetime.combine(today, preferred_time, tzinfo=ZoneInfo(tz_name))
    return local_dt.astimezone(ZoneInfo("UTC")).time()

def add_one_day(dt: datetime) -> datetime:
    return dt + timedelta(days=1)


async def get_or_create_caregiver(db: AsyncSession, phone: str, name: str):

    result = await db.execute(
        select(Caretaker).where(Caretaker.phone_number == phone)
    )
    caregiver = result.scalar_one_or_none()

    if caregiver:
        return caregiver, False

    # Create a new one
    caregiver = Caretaker(phone_number=phone, name=name)
    db.add(caregiver)
    await db.flush()
    return caregiver, True