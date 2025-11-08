import random
import string
import logging
from datetime import datetime
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

def generate_random_string(length=8):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

# Example usage:
# random_string = generate_random_string()
# print(random_string)


# Configure the hashing algorithm
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


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



async def construct_whatsapp_brain_coach_message(first_name, report_content, suggestions):
    user_score = 0
    total_max_score = 0
    scores_content = ""
    length = len(report_content) - 1
    current_date = datetime.now().strftime("%A, %B %d, %Y")
    for i, rep in enumerate(report_content):
        if rep['score'] == 1:
            user_score += 1
            symbol = '✅'
        else:
            symbol = '❌'
        if i == length:
            scores_content += f"{rep['question_type']} {symbol}"
        else:
            scores_content += f"{rep['question_type']} {symbol} \n- " 
        total_max_score += rep['max_score']
        user_score += rep['score']
    
    content = {1: first_name, 2: current_date, 3: scores_content, 4: user_score, 5: total_max_score, 6: suggestions}
    logger.info(f"Whatsapp Brain Coach Report Content Generated for {first_name}: {content}")
    return content


async def construct_email_brain_coach_message(responses, repo):
    report_content = []
    for response in responses:
        question = await repo.get_question_translation(response.question_id, 'es')
        if question:
            report_content.append({
                "question_text": question.question_text,
                "question_type": question.question_type,
                "theme": question.theme,
                'score': response.score,
                "max_score": question.max_score,
                'tier': question.tier,
                'session': question.session,
            })
        else:
            logger.warning(f"Question ID {response.question_id} not found for response ID {response.id}")

    logger.info(f'Constructed {len(report_content)} responses for email content')
    return report_content


def construct_phone_call_message(user, medication):
    pass

def construct_initial_agent_message_for_reminders(user, medication):
    return f'Hello {user['first_name']}!, this is VYVA. How are you doing?'
    # pass