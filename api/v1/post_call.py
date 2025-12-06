from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta
from fastapi import Request
from hashlib import sha256
import logging, json, pytz
from repositories.eleven_labs_sessions import ElevenLabsSessionRepository
from schemas.eleven_labs_session import ElevenLabsSessionCreate
from tasks.management_tasks import initiate_onboarding_call
from models.onboarding_user import OnboardingUser


logger = logging.getLogger(__name__)


from core.database import get_db

router = APIRouter()

@router.post("/general")
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
            user_id = conversation_initiation_client_data.get("dynamic_variables", {}).get("user_id")
            
            call_duration = metadata.get("call_duration_secs")
            termination_reason = metadata.get("termination_reason")

            call_successful = analysis.get("call_successful")
            transcript_summary = analysis.get("transcript_summary")
            

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

router.post("/onboarding")    
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

            
            callback_data = analysis.get("data_collection_results", {}).get("callback_time", {})
            if callback_data and "value" in callback_data:
                callback_time = callback_data["value"]  # e.g., "10:07"
            
            user_id = conversation_initiation_client_data.get("dynamic_variables", {}).get("user_id")
            
            if callback_time and user_id:
                try:
                    # Fetch the user from DB
                    result = await db.execute(select(OnboardingUser).where(OnboardingUser.id == user_id))
                    user = result.scalar_one_or_none()

                    if user:
                        # Determine the user's timezone, default to Europe/Paris
                        user_timezone = getattr(user, "timezone", "Europe/Paris")
                        tz = pytz.timezone(user_timezone)

                        # Current time in user's timezone
                        now = datetime.now(tz)

                        # Construct datetime for callback
                        hours, minutes = map(int, callback_time.split(":"))
                        final_dt = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                        print("FINAL_UTC_DT", final_dt)
                        # If time has already passed today, schedule for tomorrow
                        if final_dt <= now:
                            final_dt += timedelta(days=1)

                        # Convert to UTC for Celery ETA
                        final_utc_dt = final_dt.astimezone(pytz.UTC)

                        print("FINAL_UTC_DT", final_utc_dt)
                        # Schedule the Celery task
                        task_result = initiate_onboarding_call.apply_async(args=[user], eta=final_utc_dt)
                        logger.info(f"Scheduled onboarding call for {final_utc_dt} UTC, task_id={task_result.id}")
                    else:
                        logger.warning(f"User with ID {user_id} not found, cannot schedule callback.")
                except Exception as e:
                    logger.error(f"Error scheduling callback task: {e}")
            

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
    
