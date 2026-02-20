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