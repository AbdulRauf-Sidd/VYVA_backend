"""
Sends the "VYVA number has changed" SMS via Zamarda to every user whose
organization is ORGANIZATION_NAME ("Zamora").

Dry run is the default and sends nothing. Pass --send to actually send.

Run from the repo root:

    python -m scripts.broadcast_number_change_sms                 # dry run, lists recipients
    python -m scripts.broadcast_number_change_sms --limit 3       # dry run, first 3 users
    python -m scripts.broadcast_number_change_sms --send          # really send to the filtered users
"""

import argparse
import sys
import time

from sqlalchemy import func

from core.database import get_sync_session
from models.organization import Organization
from models.user import User
from services.zamarda_sms_service import zamarda_sms_service

MESSAGE = (
    "¡Hola! :wave: Nuestro número de VYVA ha cambiado. "
    "Nuestro nuevo número es ahora: *+34 856 634 672* "
    "Por favor, guarda este nuevo contacto. ¡Gracias!"
)

# Only users whose organization name equals this (case-insensitive).
ORGANIZATION_NAME = "Zamora"

# Zamarda allows 100 requests/minute; stay safely under it.
SEND_INTERVAL_SECONDS = 0.7


def _is_valid_number(phone_number: str | None) -> bool:
    if not phone_number or not phone_number.startswith("+"):
        return False
    digits = phone_number[1:]
    return digits.isdigit() and 10 <= len(digits) <= 15


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--send", action="store_true", help="Actually send. Without it this is a dry run.")
    parser.add_argument("--limit", type=int, default=None, help="Only process the first N users.")
    args = parser.parse_args()

    dry_run = not args.send

    with get_sync_session() as db:
        query = (
            db.query(User.id, User.phone_number)
            .join(Organization, User.organization_id == Organization.id)
            .filter(func.lower(Organization.name) == ORGANIZATION_NAME.lower())
            .order_by(User.id)
        )
        if args.limit:
            query = query.limit(args.limit)
        users = query.all()

    seen = set()
    recipients = []
    skipped = []
    for user_id, phone_number in users:
        if not _is_valid_number(phone_number):
            skipped.append((user_id, phone_number, "invalid number"))
        elif phone_number in seen:
            skipped.append((user_id, phone_number, "duplicate"))
        else:
            seen.add(phone_number)
            recipients.append((user_id, phone_number))

    print(f"Mode: {'DRY RUN (nothing will be sent)' if dry_run else 'LIVE SEND'}")
    print(f"Users: {len(users)} | recipients: {len(recipients)} | skipped: {len(skipped)}")
    print(f"Organization filter: {ORGANIZATION_NAME!r}")
    print(f"Message: {MESSAGE}\n")

    for user_id, phone_number, reason in skipped:
        print(f"SKIP  user={user_id} number={phone_number!r} ({reason})")

    sent = failed = 0
    for user_id, phone_number in recipients:
        if dry_run:
            print(f"WOULD SEND  user={user_id} -> {phone_number}")
            continue

        ok = zamarda_sms_service.send_sms_sync(phone_number, MESSAGE)
        print(f"{'SENT  ' if ok else 'FAILED'} user={user_id} -> {phone_number}")
        sent += ok
        failed += not ok
        time.sleep(SEND_INTERVAL_SECONDS)

    if dry_run:
        print(f"\nDry run complete. {len(recipients)} messages would be sent. Re-run with --send to send.")
    else:
        print(f"\nDone. sent={sent} failed={failed} skipped={len(skipped)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
