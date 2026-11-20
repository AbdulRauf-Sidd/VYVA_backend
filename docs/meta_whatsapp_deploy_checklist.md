# Meta WhatsApp deploy checklist (temp)

No DB migration needed.

## Before / at deploy
- [ ] `.env`: `META_WHATSAPP_ACCESS_TOKEN`, `META_WHATSAPP_PHONE_NUMBER_ID`, `META_APP_SECRET`, `META_WEBHOOK_VERIFY_TOKEN`
- [ ] Template rows (`template_id` = Meta template name), per language in use:
  - `magic_link`, `caretaker_magic_link`
  - `medication_reminder`, `ask_for_reminder`
  - `brain_coach`, `brain_coach_weekly_summary`, `brain_coach_weekly_no_activity`
  - `symptom_checker`
  - `emergency_contact_alert`
- [ ] Meta dashboard: webhook URL `https://<domain>/api/v1/whatsapp/webhook`, verify token, subscribe to `messages`
- [ ] Restart API **and** Celery worker

## Template requirements
- Body variable count must match exactly what the code sends
- `ask_for_reminder`: no body variables; `medication_reminder`: 2 (name, meds)
- Both: two quick-reply buttons, Yes then No
- Approved under `en_US`, `es`, `de`, `fr`

## Known issues
- OTP endpoints return 500 without an `otp` template (unused)
- Places WhatsApp returns `whatsapp_failed` without a `places_results` template (unused)
- Missed-medication caretaker alert reuses `medication_reminder` and will likely be rejected; needs its own template
- Meta test mode: only added recipients receive messages
- `/api/v1/twilio/incoming-message` removed

## Smoke test
1. `test_send_medication_reminder(<user_id>, '<your number>')`
2. Tap No: expect `ask_for_reminder` template
3. Tap Yes: medication log status changes
4. `test_send_weekly_brain_coach_report(<user_id>)`
5. Failures: grep logs for `Meta WhatsApp error`
