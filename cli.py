# app/cli.py
from services.services.user_service import sync_users
from services.whatsapp_service import whatsapp_service

def main():
    dic = {
        1: "https://zamora.vyva.io/verify?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9",
    }

    whatsapp_service.send_onboarding_message(
        to_phone_number="+1234567890",
        template_data=dic
    )

if __name__ == "__main__":
    main()
