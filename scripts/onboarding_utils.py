from core.database import get_sync_session
from models import User
from models.authentication import UserTempToken, CaretakerTempToken
from datetime import datetime, timedelta, timezone
from services.sms_service import sms_service
from scripts.utils import get_iso_language

USER_MESSAGE_MAP = {
    "es": "¡Bienvenido/a a VYVA! Toque este enlace para acceder: PLACEHOLDER",
    "en": "Welcome to VYVA! Tap this link to access: PLACEHOLDER",
    "de": "Willkommen bei VYVA! Tippen Sie auf diesen Link, um Zugriff zu erhalten: PLACEHOLDER"
}

CAREGIVER_MESSAGE_MAP = {
    "es": (
        "Bienvenido/a a VYVA.\n\n"
        "Toque este enlace para acceder al panel del cuidador y ver el estado de su familiar: PLACEHOLDER\n\n"
        "Si necesita ayuda, puede escribir a help@mokadigital.net"
    ),
    "en": (
        "Welcome to VYVA.\n\n"
        "Tap this link to access the caregiver dashboard and check your family member's status: PLACEHOLDER\n\n"
        "If you need help, you can write to help@mokadigital.net"
    ),
    "de": (
        "Willkommen bei VYVA.\n\n"
        "Tippen Sie auf diesen Link, um auf das Betreuungspanel zuzugreifen und den Status Ihres Familienmitglieds zu sehen: PLACEHOLDER\n\n"
        "Falls Sie Hilfe benötigen, können Sie eine E-Mail an help@mokadigital.net schreiben."
    )
}


def construct_onboarding_message_for_user(iso_language, link):
    message = USER_MESSAGE_MAP.get(iso_language)
    message = message.replace('PLACEHOLDER', link)
    return message

def construct_onboarding_message_for_caretaker(iso_language, link):
    message = CAREGIVER_MESSAGE_MAP.get(iso_language)
    message = message.replace('PLACEHOLDER', link)
    return message

def construct_onboarding_user_payload(user, agent_id) -> dict:
    if user.address or user.city_state_province or user.postal_zip_code:
        parts = [
            user.address,
            user.city_state_province,
            user.postal_zip_code
        ]
        combined_address = ", ".join([p for p in parts if p])
    else:
        combined_address = "not available"

    payload = {
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone_number": user.phone_number,
        "language": user.language,
        'user_id': user.id,
        "agent_id": agent_id,
        "address": combined_address,
        "user_type": user.preferred_communication_channel,
        "caregiver_name": user.caregiver_name,
        "caregiver_contact_number": user.caregiver_contact_number,
        "timezone": user.timezone,
        "email": user.email
    }
    return payload


def send_onboarding_sms(phone_number: str = None, user: User = None, send_to_caregiver: bool = False):
    with get_sync_session() as db:
        if not user:
            if not phone_number:
                raise ValueError("Either user or phone_number must be provided")

            user = db.query(User).filter_by(phone_number=phone_number).first()
            if not user:
                raise ValueError(f"User with phone number {phone_number} not found")

        temp_token = UserTempToken(
            user_id=user.id,
            expires_at=datetime.now(timezone.utc) + timedelta(hours=96),
            used=False
        )
        db.add(temp_token)

        # Create caregiver temp token if applicable
        temp_token_caregiver = None
        if send_to_caregiver and user.caretaker:
            temp_token_caregiver = CaretakerTempToken(
                caretaker_id=user.caretaker.id,
                expires_at=datetime.now(timezone.utc) + timedelta(hours=96),
                used=False
            )
            db.add(temp_token_caregiver)

        db.commit()

        # Send user onboarding SMS
        onboarding_link = f"https://{user.organization.sub_domain}.vyva.io/verify?token={temp_token.token}"
        iso_language = get_iso_language(user.preferred_consultation_language)
        user_message = construct_onboarding_message_for_user(iso_language, onboarding_link)
        sms_service.send_sms_sync(user.phone_number, user_message)

        # Send caregiver onboarding SMS if applicable
        if temp_token_caregiver:
            caregiver_onboarding_link = f"https://care-{user.organization.sub_domain}.vyva.io/senior-verification?token={temp_token_caregiver.token}"
            caregiver_message = construct_onboarding_message_for_caretaker(iso_language, caregiver_onboarding_link)
            sms_service.send_sms_sync(user.caretaker.phone_number, caregiver_message)