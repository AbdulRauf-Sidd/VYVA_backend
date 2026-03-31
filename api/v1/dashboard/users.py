from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from typing import List, Dict
from core.database import get_async_session
from models.user import User, Caretaker
from models.user_check_ins import UserCheckin
from models.medication import MedicationLog
from models.organization import Organization

router = APIRouter()

# Dependency to get async session
async def get_session():
    async with get_async_session() as session:
        yield session

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

    users_result = await session.execute(
        select(User).where(User.organization_id == org_id)
    )
    users: List[User] = users_result.scalars().all()

    if not users:
        return {"totalUsers": 0, "gisUsers": [], "cityDistribution": []}

    seven_days_ago = datetime.utcnow() - timedelta(days=7)

    checkins_result = await session.execute(
        select(UserCheckin).where(UserCheckin.user_id.in_([u.id for u in users]))
    )
    checkins: List[UserCheckin] = checkins_result.scalars().all()
    checkin_map = {c.user_id: c.is_active for c in checkins}

    med_logs_result = await session.execute(
        select(MedicationLog)
        .where(MedicationLog.user_id.in_([u.id for u in users]))
        .where(MedicationLog.status == "missed")
        .where(MedicationLog.created_at >= seven_days_ago)
    )
    med_logs: List[MedicationLog] = med_logs_result.scalars().all()
    missed_meds_map: Dict[int, int] = {}
    for log in med_logs:
        missed_meds_map[log.user_id] = missed_meds_map.get(log.user_id, 0) + 1

    gis_users = []
    for u in users:
        missed_meds = missed_meds_map.get(u.id, 0)
        checkin_enabled = checkin_map.get(u.id, False)
        health_conditions = len(u.health_conditions.split(",") if u.health_conditions else [])

        gis_users.append({
            "id": u.id,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "city": u.city,
            "phone": u.phone_number,
            "date_of_birth": u.date_of_birth.isoformat() if u.date_of_birth else None,
            "coords": None, 
            "activeAlerts": 0,
            "criticalAlerts": 0,
            "sensorCount": 0,
            "offlineSensors": 0,
            "checkinEnabled": checkin_enabled,
            "healthConditions": health_conditions,
            "missedMeds7d": missed_meds,
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