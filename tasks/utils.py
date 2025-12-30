from celery_app import celery_app



def schedule_reminder_message(payload, dt_utc, preferred_reminder_channel):
    if preferred_reminder_channel == "whatsapp":
        celery_app.send_task(
            "send_whatsapp_medication_reminder",
            args=[payload,],
            eta=dt_utc
        )
    elif preferred_reminder_channel == "phone":
        celery_app.send_task(
            "initiate_medication_call",
            args=[payload,],
            eta=dt_utc
        )
    elif preferred_reminder_channel == "app":
        celery_app.send_task(
            "send_app_medication_reminder",
            args=[payload,],
            eta=dt_utc
        )
    else:
        # Default to WhatsApp
        celery_app.send_task(
            "send_whatsapp_medication_reminder",
            args=[payload,],
            eta=dt_utc
        )