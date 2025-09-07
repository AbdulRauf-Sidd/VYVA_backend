from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from fastapi import Request
import time
import hmac
from hashlib import sha256

from core.database import get_db

router = APIRouter()

@router.post("/")
async def receive_message(request: Request):
    payload = await request.body()
    headers = request.headers.get("elevenlabs-signature")
    if headers is None:
        return
    # timestamp = headers.split(",")[0][2:]
    # hmac_signature = headers.split(",")[1]
    # # Validate timestamp
    # tolerance = int(time.time()) - 30 * 60
    # if int(timestamp) < tolerance:
    #     return
    # # Validate signature
    # full_payload_to_sign = f"{timestamp}.{payload.decode('utf-8')}"
    # mac = hmac.new(
    #     key=secret.encode("utf-8"),
    #     msg=full_payload_to_sign.encode("utf-8"),
    #     digestmod=sha256,
    # )
    # digest = 'v0=' + mac.hexdigest()
    # if hmac_signature != digest:
    #     return

    
    # Continue processing
    return {"status": "received"}
