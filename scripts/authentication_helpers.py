import hashlib
import random
from datetime import datetime, timedelta
from services.sms_service import sms_service

def generate_otp(length=6):
    return str(random.randint(10**(length-1), 10**length - 1))

def hash_otp(otp: str) -> str:
    return hashlib.sha256(otp.encode()).hexdigest()

def is_expired(expires_at) -> bool:
    return datetime.utcnow() > expires_at

def send_otp_via_sms(phone_number: str, otp: str):
    sms_service.send_otp(phone_number, otp)
    
def is_valid_phone_number(phone_number: str) -> bool:
    if not phone_number.startswith('+'):
        return False

    digits_only = phone_number[1:]
    if not digits_only.isdigit():
        return False

    return 10 <= len(digits_only) <= 15