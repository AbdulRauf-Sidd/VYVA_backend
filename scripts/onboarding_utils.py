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
    message = USER_MESSAGE_MAP.get(iso_language, "PLACEHOLDER")
    message = message.replace('PLACEHOLDER', link)
    return message

def construct_onboarding_message_for_caretaker(iso_language, link):
    message = CAREGIVER_MESSAGE_MAP.get(iso_language, "PLACEHOLDER")
    message = message.replace('PLACEHOLDER', link)
    return message

def construct_onboarding_user_payload(user, agent_id) -> dict:
    if user.address or user.city_state_province or user.postal_zip_code:
        combined_address = f"{user.address}, {user.city_state_province}, {user.postal_zip_code}"
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