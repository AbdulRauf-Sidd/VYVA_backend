from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from fastapi import Request
import time
import hmac
from hashlib import sha256
import logging
import json
from repositories.eleven_labs_sessions import ElevenLabsSessionRepository
from schemas.eleven_labs_session import ElevenLabsSessionCreate



logger = logging.getLogger(__name__)


from core.database import get_db

router = APIRouter()

@router.post("/")
async def receive_message(request: Request, db: AsyncSession = Depends(get_db)):

    try:
        # --- Read and decode payload ---
        raw_payload = await request.body()
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except Exception as e:
            logger.error(f"Invalid JSON payload: {e}, raw: {raw_payload}")
            return {"status": "error", "reason": "invalid_json"}

        # --- Signature verification (optional if secret provided) ---
        # if secret:
        #     try:
        #         headers = request.headers.get("elevenlabs-signature")
        #         if not headers:
        #             logger.warning("Missing signature header")
        #             return {"status": "error", "reason": "missing_signature"}

        #         timestamp, hmac_signature = headers.split(",")
        #         timestamp = timestamp[2:]  # remove `t=`
        #         hmac_signature = hmac_signature.strip()

        #         # Check tolerance (30 minutes)
        #         tolerance = int(time.time()) - 30 * 60
        #         if int(timestamp) < tolerance:
        #             logger.warning("Expired signature timestamp")
        #             return {"status": "error", "reason": "expired_signature"}

        #         full_payload_to_sign = f"{timestamp}.{raw_payload.decode('utf-8')}"
        #         mac = hmac.new(
        #             key=secret.encode("utf-8"),
        #             msg=full_payload_to_sign.encode("utf-8"),
        #             digestmod=sha256,
        #         )
        #         digest = "v0=" + mac.hexdigest()
        #         if hmac_signature != digest:
        #             logger.warning("Invalid signature")
        #             return {"status": "error", "reason": "invalid_signature"}
        #     except Exception as e:
        #         logger.error(f"Error validating signature: {e}")
        #         return {"status": "error", "reason": "signature_validation_failed"}

        # --- Extract payload fields safely ---
        try:
            type = payload.get("type")
            data = payload.get("data", {})
            event_timestamp = payload.get("event_timestamp")

            agent_id = data.get("agent_id")
            status = data.get("status")
            transcript = data.get("transcript")
            metadata = data.get("metadata", {})
            analysis = data.get("analysis", {})
            conversation_initiation_client_data = data.get("conversation_initiation_client_data", {})

            call_duration = metadata.get("call_duration_secs")
            termination_reason = metadata.get("termination_reason")

            call_successful = analysis.get("call_successful")
            transcript_summary = analysis.get("transcript_summary")

            user_id = (
                conversation_initiation_client_data
                .get("dynamic_variables", {})
                .get("user_id")
            )

        except Exception as e:
            logger.error(f"Error extracting fields: {e}, payload={payload}")
            return {"status": "error", "reason": "field_extraction_failed"}

        logger.info(
            f"Post Call Received: "
            f"Type={type}, "
            f"AgentID={agent_id}, "
            f"Status={status}, "
            f"EventTimestamp={event_timestamp}, "
            f"Duration={call_duration if metadata else 'N/A'}, "
            f"TerminationReason={termination_reason if metadata else 'N/A'}, "
            f"CallSuccessful={call_successful if analysis else 'N/A'}, "
            f"TranscriptSummary={transcript_summary if analysis else 'N/A'}, "
            f"UserID={user_id if conversation_initiation_client_data else 'N/A'}, "
            f"TranscriptLength={len(transcript) if transcript else 0}"
        )

        # --- Save to DB ---
        try:
            session_repo = ElevenLabsSessionRepository(db)
            session_data = ElevenLabsSessionCreate(
                call_successful=call_successful,
                user_id=user_id,
                agent_id=agent_id,
                duration=call_duration,
                termination_reason=termination_reason,
                summary=transcript_summary,
                transcription=transcript,
            )
            created_session = await session_repo.create(session_data)
            logger.info(f"Session saved successfully with ID {created_session.id}")
        except Exception as e:
            logger.error(f"DB insert failed: {e}")
            return {"status": "error", "reason": "db_insert_failed"}

        return {"status": "recieved"}

    except Exception as e:
        logger.exception(f"Unexpected error in handle_elevenlabs_post_call: {e}")
        return {"status": "error", "reason": "unexpected_error"}

    

