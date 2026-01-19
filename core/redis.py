ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY = "ONBOARDING_CALL_STATUS_CHECK_REDIS_KEY"
MEDICATION_REMINDER_CALL_STATUS_CHECK_REDIS_KEY = "MEDICATION_REMINDER_CALL_STATUS_CHECK_REDIS_KEY"

import redis

conn = redis.Redis(
    host="localhost",
    port=6379,
    db=0,
    decode_responses=True  # returns strings instead of bytes
)