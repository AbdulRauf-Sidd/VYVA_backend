"""
Inspect how ElevenLabs reports different call outcomes, so the status mapping
in services/elevenlabs_service.py (normalize_call_status) can be checked against
real data from the SIP trunk.

Usage (conversation IDs as args, or one per line in a file):
    python -m scripts.inspect_calls conv_abc conv_def ...
    python -m scripts.inspect_calls -f ids.txt
    python -m scripts.inspect_calls -f ids.txt --raw      # also dump full JSON per call
    python -m scripts.inspect_calls -f ids.txt --out calls.json   # save full JSON for all calls

Prints one line per call, then a summary grouping calls by their outcome
signature, with what our normalizer currently maps each signature to.
"""

import argparse
import json
import sys
from collections import defaultdict

import requests

from core.config import settings
from services.elevenlabs_service import normalize_call_status


def fetch(conversation_id: str) -> dict:
    response = requests.get(
        f"https://api.elevenlabs.io/v1/convai/conversations/{conversation_id}",
        headers={"xi-api-key": settings.ELEVENLABS_API_KEY},
        timeout=30,
    )
    if response.status_code >= 400:
        return {"_fetch_error": f"{response.status_code} {response.text[:300]}"}
    return response.json()


def signature(conv: dict) -> dict:
    """The fields that decide how a call outcome is classified."""
    metadata = conv.get("metadata") or {}
    phone_call = metadata.get("phone_call") or {}
    return {
        "status": conv.get("status"),
        "call_result": phone_call.get("call_result"),
        "call_type": phone_call.get("type"),
        "termination_reason": metadata.get("termination_reason"),
        "duration_secs": metadata.get("call_duration_secs"),
        "error": (metadata.get("error") or conv.get("error")),
        "phone_call_keys": sorted(phone_call.keys()),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("ids", nargs="*")
    parser.add_argument("-f", "--file", help="file with one conversation ID per line")
    parser.add_argument("--raw", action="store_true", help="print full JSON for each call")
    parser.add_argument("--out", help="write full JSON for all calls to this file")
    args = parser.parse_args()

    ids = list(args.ids)
    if args.file:
        with open(args.file) as f:
            ids += [line.strip() for line in f if line.strip()]
    if not ids:
        parser.error("no conversation IDs given")

    results = {}
    groups = defaultdict(list)

    for cid in ids:
        conv = fetch(cid)
        results[cid] = conv
        if "_fetch_error" in conv:
            print(f"{cid}: FETCH ERROR {conv['_fetch_error']}")
            continue

        sig = signature(conv)
        norm = normalize_call_status(conv)
        print(
            f"{cid}: status={sig['status']} call_result={sig['call_result']} "
            f"duration={sig['duration_secs']} termination={sig['termination_reason']!r} "
            f"error={sig['error']!r} -> ours={norm['status']} final={norm['is_final']}"
        )
        if args.raw:
            print(json.dumps(conv, indent=2, default=str))

        key = (sig["status"], sig["call_result"], sig["termination_reason"], norm["status"], norm["is_final"])
        groups[key].append(cid)

    print("\n=== Summary: distinct outcome signatures ===")
    for (status, call_result, termination, ours, final), cids in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        print(
            f"\n[{len(cids)} call(s)] status={status} call_result={call_result} "
            f"termination_reason={termination!r}\n    -> our status={ours} is_final={final}\n    e.g. {cids[0]}"
        )

    if args.out:
        with open(args.out, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"\nFull JSON written to {args.out}")


if __name__ == "__main__":
    sys.exit(main())
