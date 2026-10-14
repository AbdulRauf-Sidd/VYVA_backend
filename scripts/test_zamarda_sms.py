"""
Manual test: sends a plain SMS through Zamarda (Zadarma API, POST /v1/sms/send/).

Run from the repo root:

    python -m scripts.test_zamarda_sms
    python -m scripts.test_zamarda_sms +34600000000

Reads ZAMARDA_API_KEY and ZAMARDA_API_SECRET from .env / the environment.
"""

import base64
import hashlib
import hmac
import os
import sys
from urllib.parse import quote_plus, urlencode

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

API_HOST = "https://api.zadarma.com"
SMS_METHOD = "/v1/sms/send/"

TEST_NUMBER = "+923152526525"

MESSAGE = (
    "¡Hola! :wave: Nuestro número de VYVA ha cambiado. "
    "Nuestro nuevo número es ahora: *+34 856 634 672* "
    "Por favor, guarda este nuevo contacto. ¡Gracias!"
)


def _signature(method: str, params: dict, secret: str) -> str:
    params_str = urlencode(sorted(params.items()), quote_via=quote_plus)
    data = method + params_str + hashlib.md5(params_str.encode()).hexdigest()
    # Matches PHP: base64_encode(hash_hmac('sha1', $data, $secret)) - hex digest, then base64.
    hex_digest = hmac.new(secret.encode(), data.encode(), hashlib.sha1).hexdigest()
    return base64.b64encode(hex_digest.encode()).decode()


def send_sms(to_number: str, message: str, sender: str | None = None) -> bool:
    key = os.getenv("ZAMARDA_API_KEY")
    secret = os.getenv("ZAMARDA_API_SECRET")
    if not key or not secret:
        print("ZAMARDA_API_KEY / ZAMARDA_API_SECRET not set")
        return False

    # Zadarma expects digits only, no '+'.
    params = {"number": to_number.lstrip("+"), "message": message}
    if sender:
        params["sender"] = sender

    headers = {"Authorization": f"{key}:{_signature(SMS_METHOD, params, secret)}"}
    response = httpx.post(API_HOST + SMS_METHOD, data=params, headers=headers, timeout=30.0)

    print(response.status_code, response.text)
    return response.is_success and response.json().get("status") == "success"


if __name__ == "__main__":
    to_number = sys.argv[1] if len(sys.argv) > 1 else TEST_NUMBER
    ok = send_sms(to_number, MESSAGE)
    print(f"{'Sent' if ok else 'FAILED'}: {to_number}")
    sys.exit(0 if ok else 1)
