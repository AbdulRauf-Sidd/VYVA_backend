from elevenlabs import ElevenLabs
from core.config import settings
import requests
from models.organization import AgentTypeEnum, OrganizationAgents
from models.outbound_call_logs import OutboundCallLog
from services.helpers import construct_dynamic_variables_from_payload, construct_initial_agent_message_for_reminders, constuct_initial_agent_message_for_onboarding, construct_general_welcome_message
from scripts.utils import LANGUAGE_MAP, get_user_organization
from typing import Optional, Dict, Any
from core.database import get_sync_session
import json
import logging

client = ElevenLabs(
    api_key=settings.ELEVENLABS_API_KEY,
)

logger = logging.getLogger(__name__)


async def make_fall_detection_call(user):
    data = None
    success = False
    agent_id = settings.ELEVENLABS_FALL_DETECTION_AGENT_ID
    phone_number = user.get('phone_number')
    try:
        response = requests.post(
          settings.ELEVENLABS_OUTBOUND_CALL_URL,
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "agent_id": agent_id,
            "agent_phone_number_id": settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            "to_number": phone_number,
            "conversation_initiation_client_data": {
              "conversation_config_override": {
                "agent": {
                  "first_message": f"Hello, is this {user['caretaker_name']}?"
                }
              },
              "dynamic_variables": {
                "first_name": user['first_name']
              }
            }
          },
        )

        response.raise_for_status()
        data = response.json()
        success = True
        return data
    except Exception as e:
        logger.error(f"Elevenlabs fall detection call failed: {e}")
    finally:
        save_outbound_call_log(agent_id, phone_number, user, data, success)


def make_onboarding_call(payload: dict):
    data = None
    success = False
    agent_id = payload.get("agent_id")
    phone_number = payload.get("phone_number")
    try:
        id = payload.get("user_id")
        user_type = payload.get("user_type")
        email = payload.get("email")
        timezone = payload.get("timezone")
        language = payload.get("language")
        iso_language = LANGUAGE_MAP.get(language.lower(), "en")
        first_name = payload.get("first_name")
        last_name = payload.get("last_name")
        address = payload.get("address")
        caregiver_name = payload.get("caregiver_name")
        caregiver_phone = payload.get("caregiver_phone")
        initial_message = constuct_initial_agent_message_for_onboarding(first_name, iso_language)
        response = requests.post(
          settings.ELEVENLABS_OUTBOUND_CALL_URL,
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "agent_id": agent_id,
            "agent_phone_number_id": settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            "to_number": phone_number,
            "conversation_initiation_client_data": {
              "conversation_config_override": {
                "agent": {
                    "language": iso_language
                }
              },
              "dynamic_variables": {
                "user_id": id,
                "first_name": first_name,
                "last_name": last_name,
                "address": address,
                "caregiver_name": caregiver_name,
                "caregiver_phone": caregiver_phone,
                "user_type": user_type,
                "email": email,
                "timezone": timezone
              }
            }
          },
        )

        response.raise_for_status()
        data = response.json()
        success = True
        return data
    except Exception as e:
        logger.error(f"Elevenlabs onboarding call failed: {e}")
    finally:
        save_outbound_call_log(agent_id, phone_number, payload, data, success)


def make_medication_reminder_call(payload: dict):
    data = None
    success = False
    agent_id = None
    phone_number = payload.get("phone_number")
    try:
        id = payload.get("user_id")
        organization = get_user_organization(id)
        phone_number_id = organization.phone_number_id if organization.phone_number_id else settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID
        agent = next(
            (a for a in organization.agents
             if a.agent_type == AgentTypeEnum.medication_reminder.value and a.is_active),
            None
        )

        if not agent:
            raise ValueError(f"No active medication reminder agent found for organization {organization.id}")

        agent_id = agent.agent_id
        first_name = payload.get("first_name")
        # last_name = payload.get("last_name")
        language = payload.get("language")
        iso_language = LANGUAGE_MAP.get(language.lower(), "en")
        medications = payload.get("medications")
        conversation_plan = payload.get("conversation_plan")

        dynamic_variables = construct_dynamic_variables_from_payload(payload)
        dynamic_variables["medications"] = json.dumps(medications) if medications else ""

        if conversation_plan:
            dynamic_variables["conversation_plan"] = json.dumps(conversation_plan) if isinstance(conversation_plan, (dict, list)) else conversation_plan

        response = requests.post(
          settings.ELEVENLABS_OUTBOUND_CALL_URL,
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "agent_id": agent_id,
            "agent_phone_number_id": phone_number_id,
            "to_number": phone_number,
            "conversation_initiation_client_data": {
              "conversation_config_override": {
                "agent": {
                    "language": iso_language,
                }
              },
              "dynamic_variables": dynamic_variables,
            }
          },
        )

        response.raise_for_status()
        data = response.json()
        success = True
        return data
    except Exception as e:
        logger.error(f"Elevenlabs medication reminder call failed: {e}")
        return None
    finally:
        save_outbound_call_log(agent_id, phone_number, payload, data, success)
    

def make_brain_coach_call(payload: dict):
    data = None
    success = False
    agent_id = payload.get("agent_id")
    phone_number = payload.get("phone_number")
    try:
        phone_number_id = payload.get("phone_number_id") or settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID
        language = payload.get("language")
        iso_language = LANGUAGE_MAP.get(language.lower(), "en")
        conversation_plan = payload.get("conversation_plan")

        dynamic_variables = construct_dynamic_variables_from_payload(payload)
        if conversation_plan:
            dynamic_variables["conversation_plan"] = conversation_plan

        response = requests.post(
          settings.ELEVENLABS_OUTBOUND_CALL_URL,
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "agent_id": agent_id,
            "agent_phone_number_id": phone_number_id,
            "to_number": phone_number,
            "conversation_initiation_client_data": {
              "conversation_config_override": {
                "agent": {
                    "language": iso_language
                }
              },
              "dynamic_variables": dynamic_variables,
            }
          },
        )

        response.raise_for_status()
        data = response.json()
        success = True
        return data
    except Exception as e:
        logger.error(f"Elevenlabs brain coach call failed: {e}")
        return None
    finally:
        save_outbound_call_log(agent_id, phone_number, payload, data, success)
    

def make_check_up_call(payload: dict):
    data = None
    success = False
    agent_id = payload.get("agent_id")
    phone_number = payload.get("phone_number")
    try:
        phone_number_id = payload.get("phone_number_id") or settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID
        conversation_plan = payload.get("conversation_plan")
        language = payload.get("language")
        iso_language = LANGUAGE_MAP.get(language.lower(), "en")
        dynamic_variables = construct_dynamic_variables_from_payload(payload)
        if conversation_plan:
            dynamic_variables["conversation_plan"] = conversation_plan

        response = requests.post(
          settings.ELEVENLABS_OUTBOUND_CALL_URL,
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "agent_id": agent_id,
            "agent_phone_number_id": phone_number_id,
            "to_number": phone_number,
            "conversation_initiation_client_data": {
              "conversation_config_override": {
                  "agent": {
                    "language": iso_language,
                }
              },
              "dynamic_variables": dynamic_variables
            }
          },
        )

        response.raise_for_status()
        data = response.json()
        success = True
        return data
    except Exception as e:
        logger.error(f"Elevenlabs check up call failed: {e}")
        return None
    finally:
        save_outbound_call_log(agent_id, phone_number, payload, data, success)
    
def make_general_reminder_call(payload: dict):
    data = None
    success = False
    agent_id = payload.get("agent_id")
    phone_number = payload.get("phone_number")
    try:
        phone_number_id = payload.get("phone_number_id") or settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID
        language = payload.get("language")
        iso_language = LANGUAGE_MAP.get(language.lower(), "en")
        purpose = payload.get("purpose")

        dynamic_variables = construct_dynamic_variables_from_payload(payload)
        dynamic_variables["purpose"] = purpose

        response = requests.post(
            settings.ELEVENLABS_OUTBOUND_CALL_URL,
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            json={
                "agent_id": agent_id,
                "agent_phone_number_id": phone_number_id,
                "to_number": phone_number,
                "conversation_initiation_client_data": {
                    "conversation_config_override": {
                        "agent": {"language": iso_language}
                    },
                    "dynamic_variables": dynamic_variables,
                },
            },
        )

        response.raise_for_status()
        data = response.json()
        success = True
        return data
    except Exception as e:
        logger.error(f"Elevenlabs general reminder call failed: {e}")
        return None
    finally:
        save_outbound_call_log(agent_id, phone_number, payload, data, success)


# ElevenLabs phone_call.call_result -> our call status
CALL_RESULT_STATUS_MAP = {
    "answered": "answered",
    "voicemail": "no_answer",  # a voicemail pickup counts as a missed call
    "busy": "declined",
    "no_answer": "no_answer",
    "failed": "failed",
}
FINAL_CALL_STATUSES = {"answered", "declined", "no_answer", "failed"}


def normalize_call_status(conversation: dict) -> dict:
    """Map an ElevenLabs conversation payload to our call status shape."""
    metadata = conversation.get("metadata") or {}
    phone_call = metadata.get("phone_call") or {}
    call_result = phone_call.get("call_result")
    conversation_status = conversation.get("status")

    if conversation_status == "failed":
        # The conversation itself failed (e.g. agent/config error), even if the line was picked up.
        status = "failed"
    elif call_result in CALL_RESULT_STATUS_MAP:
        status = CALL_RESULT_STATUS_MAP[call_result]
    elif conversation_status in ("initiated", "in-progress", "processing"):
        status = "in_progress"
    elif conversation_status == "done":
        # Finished with no telephony result: treat as answered only if it actually ran.
        status = "answered" if (metadata.get("call_duration_secs") or 0) > 0 else "unknown"
    else:
        status = "unknown"

    return {
        "raw_status": call_result or conversation_status,
        "status": status,
        "is_final": status in FINAL_CALL_STATUSES or (status == "unknown" and conversation_status == "done"),
    }


def get_call_status_from_elevenlabs(conversation_id: str) -> dict:
    """Fetch a call's outcome from ElevenLabs. Returns {} if it could not be fetched."""
    try:
        response = requests.get(
            f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
            headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
            timeout=30,
        )
        response.raise_for_status()
        return normalize_call_status(response.json())
    except Exception as e:
        logger.error(f"Error fetching call status from ElevenLabs for conversation {conversation_id}: {e}")
        return {}


def save_outbound_call_log(agent_id: str, phone_number: str, params: dict, response: dict, success: bool):
    try:
        with get_sync_session() as db:
            db.add(OutboundCallLog(
                agent_id=agent_id or "",
                phone_number=phone_number,
                params=params,
                response=response,
                success=success,
            ))
            db.commit()
    except Exception as log_err:
        logger.error(f"Failed to write outbound call log: {log_err}")


def call_agent(agent_id: str, phone_number: str, payload: Optional[Dict[str, Any]] = None) -> dict:
    data = None
    success = False
    try:
        if not agent_id or not phone_number:
            raise ValueError("Both agent_id and phone_number are required to make the call.")

        language = payload.get("language", "en")
        iso_language = LANGUAGE_MAP.get(language.lower(), "en")
        phone_number_id = payload.get("phone_number_id", None)
        if not phone_number_id:
            phone_number_id = settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID

        # Build dynamic variables from entire payload
        dynamic_variables = {k: v for k, v in payload.items() if k != "agent_id" or k != "phone_number_id"}

        # Make the ElevenLabs API call
        response = requests.post(
            settings.ELEVENLABS_OUTBOUND_CALL_URL,
            headers={
                "xi-api-key": settings.ELEVENLABS_API_KEY
            },
            json={
                "agent_id": agent_id,
                "agent_phone_number_id": phone_number_id,
                "to_number": phone_number,
                "conversation_initiation_client_data": {
                    "conversation_config_override": {
                        "agent": {
                            "language": iso_language,
                        }
                    },
                    "dynamic_variables": dynamic_variables
                }
            },
        )

        response.raise_for_status()
        data = response.json()
        success = True
        return data
    except Exception as e:
        logger.error(f"Error calling agent {agent_id}: {str(e)}", exc_info=True)
        raise
    finally:
        save_outbound_call_log(agent_id, phone_number, payload, data, success)
