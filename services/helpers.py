import random
import string
import logging
from datetime import datetime
# from passlib.context import CryptContext

logger = logging.getLogger(__name__)

MEDICATION_REMINDER_MESSAGE_MAP = {
    'en': "hello {first_name}, this is a reminder to take your medication.",
    'es': "hola {first_name}, este es un recordatorio para tomar su medicamento."
}


ONBOARDING_MESSAGE_MAP = {
    'en': "Hello {first_name}, welcome to VYVA!",
    'es': "Hola {first_name}, ¡bienvenido a VYVA!"
}

GENERAL_MESSAGE_MAP = {
    'en': "Hello {first_name}, how are you doing?",
    'es': "Hola {first_name}, ¿cómo estás?"
}


def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def construct_whatsapp_sms_message(user):
    meds = user['medications']
    medication_detail_string = "- "
    length = len(meds)
    for i, med in enumerate(meds):
        if i == length - 1:
            medication_detail_string += med['medication_name'] + ", " + med['medication_dosage']
        else:        
            medication_detail_string += med['medication_name'] + ", " + med['medication_dosage'] + "\n- "

    content = {1: user['first_name'], 2: medication_detail_string}
    logger.info(f"Whatsapp Message Generated for User {user['user_id']}: {content}")
    return content

def construct_sms_body_from_template_for_reminders(content, language='en'):
    if language == 'en':
        return f"Hello {content[1]}, \nPlease remember to take the following medications:\n{content[2]} \n\n- VYVA"
    if language == 'es':
        return f"Hola {content[1]}, \nes hora de tus medicamentos:\n{content[2]} \n\n- VYVA"

def construct_whatsapp_brain_coach_message(
    first_name,
    report_content,
    suggestions,
):
    user_score = 0
    total_max_score = 6
    lines = []

    current_date = datetime.now().strftime("%A, %B %d, %Y")

    for rep in report_content:
        score = rep.get("score", 0)
        user_score += score
        
        question_type = rep.get("question_type", "")

        lines.append(
            f"{question_type} - {score}"
        )

    scores_content = " | ".join(lines)

    content = {
        1: first_name,
        2: current_date,
        3: scores_content,
        4: str(user_score),
        5: str(total_max_score),
        6: suggestions
    }

    return content



def construct_general_welcome_message(first_name, iso_language='en'):
    return GENERAL_MESSAGE_MAP.get(iso_language).format(first_name=first_name)

def construct_initial_agent_message_for_reminders(first_name, iso_language='en'):
    return MEDICATION_REMINDER_MESSAGE_MAP.get(iso_language).format(first_name=first_name)
    # pass

def constuct_initial_agent_message_for_onboarding(first_name, iso_language='en'):
    return ONBOARDING_MESSAGE_MAP.get(iso_language).format(first_name=first_name)

