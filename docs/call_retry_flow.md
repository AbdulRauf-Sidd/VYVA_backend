# Outbound Call Scheduling & Retry Flow

How outbound calls are scheduled, how their outcome is tracked, and when a failed call is retried. Based on `tasks/management_tasks.py`, `tasks/utils.py`, `scripts/medication_utils.py` and `services/elevenlabs_service.py`.

## Summary

| Flow | Retries? | Mechanism | Cap |
|---|---|---|---|
| Check-up call | Yes | Status poller re-queues the call 60s after a failed attempt | 3 attempts, then emergency protocol |
| Onboarding call | Yes | Hourly scan picks the user up again | 3 attempts (`call_attempts < 3`) |
| Medication reminder call | No | Status is recorded only | n/a |
| Brain coach call | No | Status is recorded; session is closed regardless of outcome | n/a |

No flow uses Celery's own retry. "Retry" always means a new task queued by our code.

## Shared pieces

- **Beat schedule** (`celery_app.py`): `schedule_calls_for_hour` and `process_pending_onboarding_users` both run at minute 0 of every hour (UTC).
- **Status polling.** After a call is placed, a poller task is queued through a Redis key so only one is pending at a time:

  | Poller | Delay | Dedup window | Used by |
  |---|---|---|---|
  | `update_scheduled_call_status` | 2 min | 120s | check-up, brain coach |
  | `update_call_status` | 5 min | 300s | medication reminders |
  | `check_onboarding_call_status` | 5 min | 300s | onboarding |

- **Call outcome** comes from `get_call_status_from_elevenlabs`, normalised by `normalize_call_status` into `answered`, `declined`, `no_answer`, `failed`, `in_progress` or `unknown`, plus an `is_final` flag. If the status can't be fetched, the poller keeps the previous status and tries again on its next run.

## Check-up calls

```
hourly: schedule_calls_for_hour
   └─ schedule_check_in_calls_for_hour
        for each active check-in whose local time falls in this UTC hour:
          skip if frequency not elapsed, or a non-"unconfirmed" log exists today
          create CheckinLog(status=unconfirmed)
          send_task(initiate_check_up_call, eta=check-in time)
          create ScheduledSession(attempts=0)

initiate_check_up_call(check_in_id)
   ├─ skip if latest CheckinLog is no longer "unconfirmed" (user already reported)
   ├─ skip if no pending ScheduledSession, or no check-in agent for the org
   ├─ place call
   └─ on response: session.attempts += 1, save call_sid, queue status poller

update_scheduled_call_status (poller)
   for each session with a call_sid, not completed:
     not final        -> keep polling
     answered / other -> session completed
     declined | no_answer | failed:
        attempts < 3  -> initiate_check_up_call (countdown 60s)   <- the retry
        attempts >= 3 -> emergency WhatsApp + emergency outbound agent
                         (unless user.emergency_protocol_after_3_missed_checkins is False)
                         session completed
```

Notes:
- `attempts` only increments when the call was initiated (a response came back). A call that fails to initiate is not counted and is not retried that day.
- The "skip if log is no longer unconfirmed" check is what stops retries once the user has reported in.

## Onboarding calls

```
hourly: process_pending_onboarding_users
   select OnboardingUser where:
       onboarding_status == False
       onboarding_call_scheduled == False
       call_attempts < 3
       consent_given is not False
   skip if call_back_date_time is on a later local date
   send_task(initiate_onboarding_call, payload)
   set onboarding_call_scheduled = True

initiate_onboarding_call(payload)
   place call
   onboarding_call_scheduled = False
   call_attempts += 1, called_at = now
   no response  -> save the attempt and stop
   response     -> create OnboardingLogs(status=in_progress), queue check_onboarding_call_status

check_onboarding_call_status (poller)
   updates OnboardingLogs.status only; does not retry
```

Notes:
- The retry is implicit: because `onboarding_call_scheduled` goes back to `False` and `call_attempts < 3`, the user is picked up again by the next hourly scan, whatever happened on the call.
- After 3 attempts the user is no longer selected.
- The retry does not check the previous call's outcome. A user who answered but did not finish onboarding is called again the same way as one who did not pick up.

## Medication reminder calls

```
hourly: schedule_calls_for_hour
   └─ schedule_medication_reminders_for_hour
        groups due doses per user for this UTC hour
        send_task(initiate_medication_reminder_call, eta=dose time)

initiate_medication_reminder_call(payload)
   create medication logs, build conversation plan, place call
   on response: create ElevenLabsSessions(status="ringing"), queue update_call_status
   no response: log an error

update_call_status (poller)
   copies the ElevenLabs status onto each ElevenLabsSessions row
   (the block that would mark the medication "unconfirmed" on a failed call is commented out)
```

There is no retry. A missed or failed call is not re-attempted.

## Brain coach calls

Scheduled through the same check-in scheduler as check-up calls (`initiate_brain_coach_session`). A `CheckinLog` is created when the call starts. `update_scheduled_call_status` marks the session completed once the call is final, whether it was answered or not. There is no retry.

## Emergency calls

There are two separate paths that place emergency calls. Both use the organization's `emergency_responder` agent (`OrganizationAgents`, `is_active`) and the shared `call_agent` helper in `services/elevenlabs_service.py`.

### Path 1: escalation after 3 missed check-up calls

Triggered from `update_scheduled_call_status` (see "Check-up calls") when a check-up call ends `no_answer` or `failed` and `session.attempts >= 3`.

```
update_scheduled_call_status
   └─ if user.emergency_protocol_after_3_missed_checkins is not False:
        ├─ send_emergency_alert_whatsapp(user_id)     (task)
        └─ call_emergency_outbound_agent(user_id)     (task)
      session completed

send_emergency_alert_whatsapp
   skip if not user.emergency_call_to_caretaker, or no caretaker
   send WhatsApp template "emergency_contact_alert" to the caretaker
     {1} = user's first name, {2} = "did not answer our check-in call" (localised en/es/de)

call_emergency_outbound_agent
   find the org's emergency_responder agent
   payload = full_name, address, phone_number, emergency message, language, phone_number_id
   if user.emergency_call_to_caretaker  -> call_agent(caretaker phone)
   if user.emergency_call_to_government_services
        -> look up EmergencyNumber(org, type=check_in_misses) -> call_agent(that number)
```

User flags involved: `emergency_protocol_after_3_missed_checkins` (gates the whole escalation), `emergency_call_to_caretaker`, `emergency_call_to_government_services`. All are nullable booleans defaulting to `True`.

Timing: attempts are 60s apart plus poller latency (about 2 minutes per cycle), so escalation can fire roughly 5 to 10 minutes after the first missed call.

### Path 2: `emergency_responder` MCP tool (agent-initiated)

Called by a conversational agent during a call (`mcp_tools/user.py`) with `user_id` and `emergency_message`.

```
emergency_responder(user_id, emergency_message)
   404 if user not found; 403 if user.emergency_protocol_status is False; 400 if no organization
   404 if the org has no active emergency_responder agent
   payload = full_name, address, phone_number, emergency_message, language, phone_number_id
   if user.emergency_call_to_caretaker (and a caretaker exists) -> call_agent(caretaker phone)
   if user.emergency_call_to_government_services
        -> look up EmergencyNumber(org, type=emergency_call) -> call_agent(that number)
```

Difference between the paths: Path 1 uses the `check_in_misses` number and the `emergency_protocol_after_3_missed_checkins` flag; Path 2 uses the `emergency_call` number and the `emergency_protocol_status` flag.

### Bugs found and fixed

These were found by reading the code and fixed without being run against production.

**Path 1 (`tasks/management_tasks.py`)**

- **Caretaker WhatsApp.** `send_emergency_alert_whatsapp` passed a database row as the template ID and sent through Twilio. It now looks up the active `emergency_contact_alert` template (organization-specific first, then global) with `send_meta_template_by_type` and sends through Meta. A missing template or a send failure is logged and no longer crashes the task.
- **Isolated calls.** `call_emergency_outbound_agent` builds a list of targets (caretaker, emergency number) and places each call in its own `try/except`, so one failure doesn't stop the other. It returns early with a log line if the user, organization or `emergency_responder` agent is missing.
- **Master switch.** Escalation now also requires `emergency_protocol_status is not False`, matching the MCP tool. The check lives in one helper, `_escalate_missed_checkins`.
- **NULL flags.** All emergency flags are checked with `is not False`, so `NULL` means enabled everywhere, as the column defaults intend.
- **Failed initiation.** When `initiate_check_up_call` cannot start a call, it now counts it as an attempt and retries after 60 seconds. After 3, it escalates and closes the session, instead of stalling with `attempts` stuck at 0.
- **Tracking.** Each emergency call is recorded in `ElevenLabsSessions` (`agent_type=emergency_responder`) and picked up by `update_call_status`, so its outcome is stored. There is still **no retry** if the caretaker or emergency number doesn't answer. Add one if you want a policy for it.

**Path 2 (`mcp_tools/user.py`)**

- `success` is gone. The tool builds the same target list, places each call in its own `try/except`, and returns 500 only if no call could be placed. It returns 200 with the list of who was called otherwise.
- A missing emergency number no longer results in a call to `None`. It is logged and skipped. If there is nobody to call, it returns 400.
- The number lookup uses `.scalars().first()`, so several `emergency_call` numbers no longer raise.
- The blocking `call_agent` runs in `asyncio.to_thread` so it doesn't block the event loop.

**Shared (`services/elevenlabs_service.py`)**

- The dynamic-variable filter now uses `not in ("agent_id", "phone_number_id")`.
- `call_agent` raises when ElevenLabs answers 200 with `success: false`, so a failed dial is no longer treated as a placed call.
- Null dynamic variables causing a 400 are known and intentionally left as is.

## Gaps to be aware of

1. **Failed initiation on check-up calls is never retried.** If the call request fails, `attempts` is not incremented, no call SID is saved and no poller is queued, so the pending session sits until the next scheduling cycle.
2. **HTTP 200 with `success: false`.** ElevenLabs can return 200 with `{"success": false, ...}` for a dial failure. `raise_for_status()` does not catch it, so the call functions treat it as a started call. The failure is only found when the poller runs.
3. **No medication reminder retry**, and nothing ties a failed reminder call to the caregiver notification in this flow.
4. **Onboarding retry is time-based, not outcome-based.** Up to 3 hourly attempts regardless of how earlier calls ended.
