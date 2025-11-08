from elevenlabs import ElevenLabs, OutboundCallRecipient, ConversationConfigOverrideConfig
from core.config import settings
import requests

client = ElevenLabs(
    api_key=settings.ELEVENLABS_API_KEY,
)

import logging
logger = logging.getLogger(__name__)

async def make_reminder_call_batch(users: list):
    try:
        recipients = []
        for user in users:
            medication_details = user['medications']
            med_names = ''
            med_dosage = ''
            for med in medication_details:
                med_names += med['medication_name'] + " "
                med_dosage += med['medication_dosage'] + " "
            # initial_message = construct_initial_agent_message_for_reminders(user)
            phone_number = user['phone_number']
            recipients.append(OutboundCallRecipient(
                phone_number=phone_number,
                dynamic_variables={
                    "user_id": user['user_id'],
                    'first_name': user['first_name'],
                    'medication_names': med_names,
                    'medication_dosage': med_dosage,
                    'caretaker_alert': user['wants_caretaker_alerts']
                }
            ))

        obj = client.conversational_ai.batch_calls.create(
            call_name="Medication Reminder Batch",
            agent_id=settings.ELEVENLABS_MEDICATION_AGENT_ID,
            agent_phone_number_id=settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            scheduled_time_unix=1,
            recipients=recipients
        )

        logger.info(f"Initiated {len(recipients)} reminder calls via ElevenLabs with batch id: {obj.id}.")

        return obj.id
    except Exception as e:
        logger.error(f"Elevenlabs batch call failed: {e}")


async def make_caretaker_call_batch(users: list):
    try:
        recipients = []
        for user in users:
            user_id = user['user_id']
            first_name = user['first_name']
            caretaker_name = user['caretaker_name']
            phone_number = user['caretaker_phone_number']

            recipients.append({
                "phone_number": phone_number,
                "conversation_initiation_client_data": {
                  "dynamic_variables": {
                      "user_id": user_id,
                      'first_name': first_name,
                  },
                  "conversation_config_override": {
                    "agent": {
                      "first_message": f"Hello, is this {caretaker_name}?"
                    }
                  }
                }
            })

        logger.info(f'making caretaker batch for {len(recipients)} users')

        response = requests.post(
          "https://api.elevenlabs.io/v1/convai/batch-calling/submit",
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "call_name": "Medication Reminder Caretaker Batch",
            "agent_id": settings.ELEVENLABS_EMERGENCY_AGENT_ID,
            "agent_phone_number_id": settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            "scheduled_time_unix": 1,
            "recipients": recipients
          },
        )

        logger.info(f"Initiated {len(recipients)} reminder calls via ElevenLabs with response: {response}.")

    except Exception as e:
        logger.error(f"Elevenlabs batch call failed: {e}")



async def make_fall_detection_call(user):
    try:
        # Outbound call via twilio (POST /v1/convai/twilio/outbound-call)
        response = requests.post(
          "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "agent_id": settings.ELEVENLABS_FALL_DETECTION_AGENT_ID,
            "agent_phone_number_id": settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            "to_number": user['phone_number'],
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

        logger.info(f"Call response for fall detection: {response.json()}")
        
        return response.json
    except Exception as e:
        logger.error(f"Elevenlabs fall detection call failed: {e}")


async def make_emergency_call(user):
    try:
        # Outbound call via twilio (POST /v1/convai/twilio/outbound-call)
        response = requests.post(
          "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "agent_id": settings.ELEVENLABS_EMERGENCY_AGENT_ID,
            "agent_phone_number_id": settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            "to_number": user['phone_number'],
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

        logger.info(f"Call response for fall detection: {response.json()}")
        
        return response.json
    except Exception as e:
        logger.error(f"Elevenlabs fall detection call failed: {e}")



async def check_batch_for_missed(batch_id):
    batch = client.conversational_ai.batch_calls.get(
      batch_id=batch_id,
    )
    missed_phones = set()
    if batch:
        batch_status = batch.status
        if batch_status == 'completed':
            for reciepent in batch.recipients:
                if reciepent.status in ("initiated", "voicemail"):
                    missed_phones.add(reciepent.phone_number)

    return missed_phones


async def make_onboarding_call(user):
    try:
        id = user.id
        organization = user.organization
        agent_id = organization.onboarding_agent_id
        phone_number = user.phone_number
        first_name = user.first_name
        last_name = user.last_name
        response = requests.post(
          "https://api.elevenlabs.io/v1/convai/twilio/outbound-call",
          headers={
            "xi-api-key": settings.ELEVENLABS_API_KEY
          },
          json={
            "agent_id": agent_id,
            "agent_phone_number_id": settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            "to_number": phone_number,
            "conversation_initiation_client_data": {
              "dynamic_variables": {
                "user_id": id,
                "first_name": first_name,
                "last_name": last_name
              }
            }
          },
        )

        logger.info(f"Call response for onboarding call: {response.json()}")
        
        return response.json
    except Exception as e:
        logger.error(f"Elevenlabs onboarding call failed: {e}")
                    
        
          
        