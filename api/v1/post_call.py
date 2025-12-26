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
from models.onboarding import OnboardingUser
from repositories.symptom_checker import SymptomCheckerRepository
from schemas.symptom_checker import SymptomCheckerInteractionCreate
from core.config import settings


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
            
            user_id = conversation_initiation_client_data.get("dynamic_variables").get("user_id")
            
            if callback_time:
                try:
                    result = await db.execute(select(OnboardingUser).where(OnboardingUser.id == user_id))
                    user = result.scalar_one()

                    if user:
                        user_timezone = user.timezone
                        tz = pytz.timezone(user_timezone)

                        now = datetime.now(tz)

                        hours, minutes = map(int, callback_time.split(":"))
                        final_dt = now.replace(hour=hours, minute=minutes, second=0, microsecond=0)
                    
                        if final_dt <= now:
                            final_dt += timedelta(days=1)

                        final_utc_dt = final_dt.astimezone(pytz.UTC)

                        task_result = initiate_onboarding_call.apply_async(args=[user], eta=final_utc_dt)
                        logger.info(f"Scheduled onboarding call for {final_utc_dt} UTC, task_id={task_result.id}")
                    else:
                        logger.warning(f"User with ID {user_id} not found, cannot schedule callback.")
                except Exception as e:
                    logger.error(f"Error scheduling callback task: {e}")
            

        except Exception as e:
            logger.error(f"Error extracting fields: {e}, payload={payload}")
            return {"status": "error", "reason": "field_extraction_failed"}

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


@router.post("/symptom-checker")
async def receive_symptom_checker_message(request: Request, db: AsyncSession = Depends(get_db)):
    """
    Webhook endpoint for ElevenLabs symptom checker agent.
    Receives call completion data including vitals (heart rate, respiratory rate) and saves to database.
    """
    try:
        # --- Read and decode payload ---
        raw_payload = await request.body()
        try:
            payload = json.loads(raw_payload.decode("utf-8"))
        except Exception as e:
            logger.error(f"Invalid JSON payload: {e}, raw: {raw_payload}")
            return {"status": "error", "reason": "invalid_json"}

        # --- Extract payload fields safely ---
        try:
            event_type = payload.get("type")
            data = payload.get("data", {})
            event_timestamp = payload.get("event_timestamp")

            agent_id = data.get("agent_id")
            call_status = data.get("status")
            transcript = data.get("transcript", "")
            metadata = data.get("metadata", {})
            analysis = data.get("analysis", {})
            conversation_initiation_client_data = data.get("conversation_initiation_client_data", {})
            
            # Extract user_id from dynamic variables
            dynamic_variables = conversation_initiation_client_data.get("dynamic_variables", {})
            user_id = dynamic_variables.get("user_id")
            
            # Extract call metadata
            call_duration_secs = metadata.get("call_duration_secs")
            termination_reason = metadata.get("termination_reason")
            
            # Extract AI summaries
            transcript_summary = analysis.get("transcript_summary")
            call_successful = analysis.get("call_successful", False)
            
            # Extract vitals from data_collection_results
            data_collection_results = analysis.get("data_collection_results", {})
            
            # Parse vitals data (heart_rate and respiratory_rate)
            vitals_data = {}
            vitals_ai_summary = None
            symptoms_ai_summary = None
            
            # Extract heart_rate if available
            heart_rate_data = data_collection_results.get("heart_rate", {})
            if heart_rate_data and "value" in heart_rate_data:
                vitals_data["heart_rate"] = {
                    "value": heart_rate_data.get("value"),
                    "unit": heart_rate_data.get("unit", "bpm"),
                    "confidence": heart_rate_data.get("confidence"),
                    "timestamp": heart_rate_data.get("timestamp")
                }
            
            # Extract respiratory_rate if available
            respiratory_rate_data = data_collection_results.get("respiratory_rate", {})
            if respiratory_rate_data and "value" in respiratory_rate_data:
                vitals_data["respiratory_rate"] = {
                    "value": respiratory_rate_data.get("value"),
                    "unit": respiratory_rate_data.get("unit", "breaths/min"),
                    "confidence": respiratory_rate_data.get("confidence"),
                    "timestamp": respiratory_rate_data.get("timestamp")
                }
            
            # Extract AI summaries if available
            vitals_ai_summary = data_collection_results.get("vitals_summary") or analysis.get("vitals_ai_summary")
            symptoms_ai_summary = analysis.get("symptoms_ai_summary") or transcript_summary
            
            # Generate conversation_id from call_id or use event_timestamp
            call_id = metadata.get("call_id") or data.get("call_id")
            conversation_id = call_id if call_id else f"symptom_check_{event_timestamp}"
            
            # Parse call_timestamp
            call_timestamp = None
            if event_timestamp:
                try:
                    # Try parsing ISO format timestamp
                    call_timestamp = datetime.fromisoformat(event_timestamp.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    try:
                        # Try parsing Unix timestamp
                        call_timestamp = datetime.fromtimestamp(float(event_timestamp))
                    except (ValueError, TypeError):
                        call_timestamp = datetime.utcnow()
            else:
                call_timestamp = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error extracting fields: {e}, payload={payload}")
            return {"status": "error", "reason": "field_extraction_failed"}

        # --- Verify agent_id is symptom checker agent ---
        if settings.ELEVENLABS_SYMPTOM_CHECKER_AGENT_ID and agent_id != settings.ELEVENLABS_SYMPTOM_CHECKER_AGENT_ID:
            logger.warning(f"Agent ID {agent_id} does not match symptom checker agent ID {settings.ELEVENLABS_SYMPTOM_CHECKER_AGENT_ID}")
            # Continue anyway - might be useful for debugging

        logger.info(
            f"Symptom Checker Webhook Received: "
            f"Type={event_type}, "
            f"AgentID={agent_id}, "
            f"Status={call_status}, "
            f"UserID={user_id}, "
            f"ConversationID={conversation_id}, "
            f"Duration={call_duration_secs if call_duration_secs else 'N/A'}, "
            f"CallTimestamp={call_timestamp}, "
            f"VitalsData={bool(vitals_data)}, "
            f"VitalsAISummary={bool(vitals_ai_summary)}, "
            f"SymptomsAISummary={bool(symptoms_ai_summary)}"
        )

        # --- Save to SymptomCheckerResponse table using repository ---
        try:
            repo = SymptomCheckerRepository(db)
            
            # Create interaction data schema
            interaction_data = SymptomCheckerInteractionCreate(
                user_id=user_id,
                conversation_id=conversation_id,
                call_duration_secs=call_duration_secs,
                call_timestamp=call_timestamp,
                vitals_data=vitals_data if vitals_data else None,
                vitals_ai_summary=vitals_ai_summary,
                symptoms_ai_summary=symptoms_ai_summary,
                symptoms=transcript[:500] if transcript else None,  # Truncate if too long
                status="success" if call_successful else "error"
            )
            
            # Repository handles create/update logic
            saved_interaction = await repo.create_interaction(interaction_data)
            logger.info(f"Symptom checker interaction saved with ID {saved_interaction.id}")
            
        except Exception as e:
            logger.error(f"DB insert/update failed: {e}", exc_info=True)
            return {"status": "error", "reason": "db_insert_failed"}

        return {"status": "received", "conversation_id": conversation_id}

    except Exception as e:
        logger.exception(f"Unexpected error in symptom checker webhook: {e}")
        return {"status": "error", "reason": "unexpected_error"}
    

#wsec_199aa858211b8d40b792510a46885579a8c7986056bb21e476e0dfcd5d9be3aa