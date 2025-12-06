from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.ext.asyncio import AsyncSession
from models.organization import Organization
from sqlalchemy import select
from core.database import get_db
from services.email_service import email_service
import logging


router = APIRouter()


@router.get("/", status_code=status.HTTP_200_OK, summary="Get All Organizations")
async def get_organization_info(db: AsyncSession = Depends(get_db)):
    try:
        result = await db.execute(select(Organization).where(Organization.is_active == True))
        organizations = result.scalars().all()
        body = []
        for org in organizations:
            body.append({
                "id": org.id,
                "name": org.name,
                "is_active": org.is_active,
            })
        return {
            "success": True,
            "data": body
        }
    except Exception as e:
        logging.error(f"Error fetching organizations: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")