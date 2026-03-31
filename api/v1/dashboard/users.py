from fastapi import APIRouter, Depends, HTTPException, Query, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from core.database import get_async_session
from models.user import User, Caretaker
from models.user_check_ins import UserCheckin
from models.medication import MedicationLog, Medication
from models.organization import Organization
from sqlalchemy.orm import selectinload
from sqlalchemy import delete, update
from datetime import datetime, time
from zoneinfo import ZoneInfo

GERMAN_TZ = ZoneInfo("Europe/Berlin")

router = APIRouter()

async def get_session():
    async with get_async_session() as session:
        yield session

def to_cet(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    # assume dt is UTC if naive
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(GERMAN_TZ).isoformat()


def to_cet_time(t: Optional[time]) -> Optional[str]:
    if t is None:
        return None

    # attach a dummy date
    dt = datetime.combine(datetime.utcnow().date(), t)

    # assume stored in UTC
    dt = dt.replace(tzinfo=ZoneInfo("UTC"))

    return dt.astimezone(GERMAN_TZ).strftime("%H:%M")

def compute_risk_score(user_data: dict) -> int:
    score = 0
    score += user_data.get("critical_alerts", 0) * 4
    score += user_data.get("active_alerts", 0) * 2
    score += user_data.get("missed_meds_7d", 0) * 3
    score += 1 if not user_data.get("checkin_enabled") else 0
    score += user_data.get("offline_sensors", 0)
    score += user_data.get("health_conditions", 0)
    return score

@router.get("/users")
async def get_redcross_gis_users(session: AsyncSession = Depends(get_session)):
    # 1️⃣ Fetch Red Cross org
    org_result = await session.execute(
        select(Organization).where(Organization.name.ilike("Red Cross"))
    )
    redcross_org = org_result.scalars().first()

    if not redcross_org:
        return {
            "totalUsers": 0,
            "checkinsEnabled": 0,
            "activeAlertCount": 0,
            "criticalAlertCount": 0,
            "totalSensors": 0,
            "caregiversLinked": 0,
            "gisUsers": [],
            "activeAlerts": [],
            "cityDistribution": []
        }

    org_id = redcross_org.id

    # 2️⃣ Fetch users with caretakers and medications
    users_result = await session.execute(
        select(User)
        .where(User.organization_id == org_id)
        .options(
            selectinload(User.caretaker),
            selectinload(User.medications),
        )
    )
    users: List[User] = users_result.scalars().all()
    if not users:
        return {"totalUsers": 0, "gisUsers": [], "cityDistribution": []}

    user_ids = [u.id for u in users]
    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    # 3️⃣ Fetch all check-ins
    checkins_result = await session.execute(
        select(UserCheckin).where(UserCheckin.user_id.in_(user_ids))
    )
    checkins: List[UserCheckin] = checkins_result.scalars().all()

    # Maps for check-in statuses
    checkin_map = {c.user_id: c.is_active for c in checkins}
    brain_coach_map = {c.user_id: True for c in checkins if c.check_in_type == "brain_coach"}

    # 4️⃣ Fetch missed meds in last 7 days
    med_logs_result = await session.execute(
        select(MedicationLog)
        .where(MedicationLog.user_id.in_(user_ids))
        .where(MedicationLog.status == "missed")
        .where(MedicationLog.created_at >= seven_days_ago)
    )
    med_logs: List[MedicationLog] = med_logs_result.scalars().all()
    missed_meds_map: Dict[int, int] = {}
    for log in med_logs:
        missed_meds_map[log.user_id] = missed_meds_map.get(log.user_id, 0) + 1

    # 5️⃣ Build GIS users
    gis_users = []
    for u in users:
        missed_meds = missed_meds_map.get(u.id, 0)
        checkin_enabled = checkin_map.get(u.id, False)
        brain_coach_enabled = brain_coach_map.get(u.id, False)  # ✅ Updated logic
        health_conditions = len(u.health_conditions.split(",") if u.health_conditions else [])
        meds_count = len([m for m in u.medications if m.is_active])

        gis_users.append({
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "city": u.city,
            "phone": u.phone_number,
            "date_of_birth": to_cet(u.date_of_birth) if u.date_of_birth else None,
            "coords": None,
            "activeAlerts": 0,
            "criticalAlerts": 0,
            "sensorCount": 0,
            "offlineSensors": 0,
            "checkinEnabled": checkin_enabled,
            "brainCoachEnabled": brain_coach_enabled,
            "healthConditions": health_conditions,
            "missedMeds7d": missed_meds,
            "medsCount": meds_count,
            "riskScore": compute_risk_score({
                "critical_alerts": 0,
                "active_alerts": 0,
                "missed_meds_7d": missed_meds,
                "checkin_enabled": checkin_enabled,
                "offline_sensors": 0,
                "health_conditions": health_conditions,
            }),
            "caretakerNames": [u.caretaker.name] if u.caretaker else [],
        })

    total_users = len(users)
    checkins_enabled = sum(1 for u in gis_users if u["checkinEnabled"])
    active_alerts = sum(u["activeAlerts"] for u in gis_users)
    total_sensors = sum(u["sensorCount"] for u in gis_users)
    caregivers_linked = sum(1 for u in gis_users if u["caretakerNames"])

    return {
        "totalUsers": total_users,
        "checkinsEnabled": checkins_enabled,
        "activeAlertCount": active_alerts,
        "criticalAlertCount": 0,
        "totalSensors": total_sensors,
        "caregiversLinked": caregivers_linked,
        "gisUsers": gis_users,
        "activeAlerts": [],
        "cityDistribution": [
            {"city": city, "count": len([u for u in gis_users if u["city"] == city])}
            for city in set(u["city"] or "Unknown" for u in gis_users)
        ]
    }
    
def to_cet_date(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo("UTC"))
    return dt.astimezone(GERMAN_TZ).date().isoformat()
    
@router.get("/user-info")
async def get_user(
    user_id: Optional[int] = Query(None),
    organization_name: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    if not user_id and not organization_name:
        raise HTTPException(status_code=400, detail="Provide at least user_id or organization_name")

    query = select(User).options(
        selectinload(User.organization),
        selectinload(User.medications).selectinload(Medication.times_of_day),
        selectinload(User.user_checkins),
        selectinload(User.caretaker),
    )

    if user_id:
        query = query.where(User.id == user_id)

    if organization_name:
        query = query.join(User.organization).where(Organization.name.ilike(organization_name))

    result = await session.execute(query)  # ✅ FIXED
    user: User = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    caregivers = []
    if user.caretaker:
        caregivers.append({
            "id": user.caretaker.id,
            "caretaker_name": user.caretaker.name,
            "caretaker_phone": user.caretaker.phone_number,
        })

    medications = []
    for m in user.medications:
        medications.append({
            "id": m.id,
            "medication_name": m.name,
            "purpose": m.purpose,
            "dosage": m.dosage,
            "schedule_times": [
                t.time_of_day.strftime("%H:%M") for t in (m.times_of_day or []) if t.time_of_day
            ]
        })

    checkins = None
    brain_coach = None

    for c in user.user_checkins:
        data = {
            "enabled": c.is_active,
            "frequency": f"{c.check_in_frequency_days} days",
            "preferred_time": to_cet_time(c.check_in_time),
        }

        if c.check_in_type == "check_up_call":
            checkins = data
        elif c.check_in_type == "brain_coach":
            brain_coach = data

    health_conditions = (
        user.health_conditions.split(",") if user.health_conditions else []
    )

    mobility = (
        user.mobility.split(",") if user.mobility else []
    )

    return {
        "user": {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "photo_url": None,  # not in model → hardcoded
            "phone": user.phone_number,
            "date_of_birth": to_cet_date(user.date_of_birth) if user.date_of_birth else None,
            "gender": None,  # not in model
            "language": user.preferred_consultation_language,
            "timezone": user.timezone,
            "street": user.street,
            "house_number": user.house_number,
            "post_code": user.postal_code,
            "city": user.city,
            "emergency_notes": None,  # not in model
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },

        "consent": {
            "consent_given": True,  # not in model → hardcoded
            "caretaker_consent": user.caretaker_consent,
            "created_at": user.created_at.isoformat() if user.created_at else None,
        },

        "health": {
            "health_conditions": health_conditions,
            "mobility_needs": mobility,
        },

        "medications": medications,

        "checkins": checkins,
        "brainCoach": brain_coach,

        "caregivers": caregivers,

        # ❗ Not in your models → hardcoded for now
        "sensors": [],
        "alerts": [],
        "readings": [],
    }
    
@router.delete("/medications/{med_id}")
async def delete_medication(
    med_id: int,
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Medication).where(Medication.id == med_id)
    )
    med = result.scalars().first()

    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    await session.delete(med)
    await session.commit()

    return {"message": "Medication deleted successfully"}

@router.delete("/caregivers/{caregiver_id}")
async def delete_caregiver(
    caregiver_id: int,
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Caretaker).where(Caretaker.id == caregiver_id)
    )
    caregiver = result.scalars().first()

    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    await session.delete(caregiver)
    await session.commit()

    return {"message": "Caregiver deleted successfully"}

@router.put("/users/{user_id}")
async def update_user(
    user_id: int,
    payload: dict = Body(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    for key, value in payload.items():
        if hasattr(user, key) and value is not None:
            setattr(user, key, value)

    await session.commit()
    await session.refresh(user)

    return {"message": "User updated successfully"}

@router.put("/medications/{med_id}")
async def update_medication(
    med_id: int,
    payload: dict = Body(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Medication).where(Medication.id == med_id)
    )
    med = result.scalars().first()

    if not med:
        raise HTTPException(status_code=404, detail="Medication not found")

    for key, value in payload.items():
        if hasattr(med, key) and value is not None:
            setattr(med, key, value)

    await session.commit()
    await session.refresh(med)

    return {"message": "Medication updated"}

@router.put("/caregivers/{caregiver_id}")
async def update_caregiver(
    caregiver_id: int,
    payload: dict = Body(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(Caretaker).where(Caretaker.id == caregiver_id)
    )
    caregiver = result.scalars().first()

    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    for key, value in payload.items():
        if hasattr(caregiver, key) and value is not None:
            setattr(caregiver, key, value)

    await session.commit()
    await session.refresh(caregiver)

    return {"message": "Caregiver updated"}

@router.put("/checkins/{checkin_id}")
async def update_checkin(
    checkin_id: int,
    payload: dict = Body(...),
    session: AsyncSession = Depends(get_session)
):
    result = await session.execute(
        select(UserCheckin).where(UserCheckin.id == checkin_id)
    )
    checkin = result.scalars().first()

    if not checkin:
        raise HTTPException(status_code=404, detail="Checkin not found")

    for key, value in payload.items():
        if hasattr(checkin, key) and value is not None:
            setattr(checkin, key, value)

    await session.commit()
    await session.refresh(checkin)

    return {"message": "Checkin updated"}