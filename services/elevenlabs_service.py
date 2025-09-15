from elevenlabs import ElevenLabs, OutboundCallRecipient
from core.config import settings

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
            call_name="Medication Reminder Batch Calls",
            agent_id=settings.ELEVENLABS_MEDICATION_AGENT_ID,
            agent_phone_number_id=settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            scheduled_time_unix=1,
            recipients=recipients
        )

        logger.info(f"Initiated {len(recipients)} reminder calls via ElevenLabs with batch id: {obj.id}.")

        return obj.id
    except Exception as e:
        logger.error(f"Elevenlabs batch call failed: {e}")



async def make_fall_detection_batch(users):
    try:
        
        objects = OutboundCallRecipient(
            phone_number=users['phone_number']
        ) 
        
        obj = client.conversational_ai.batch_calls.create(
            call_name="Fall Dectection Batch Calls",
            agent_id=settings.ELEVENLABS_MEDICATION_AGENT_ID,
            agent_phone_number_id=settings.ELEVENLABS_AGENT_PHONE_NUMBER_ID,
            scheduled_time_unix=1,
            recipients=objects
        )

        logger.info(f"Called on {users['phone_number']}")

        return obj.id
    except Exception as e:
        logger.error(f"Elevenlabs fall detection call failed: {e}")
