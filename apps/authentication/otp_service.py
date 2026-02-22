"""
OTP Service for phone number verification
Uses MongoDB for persistent OTP storage so OTPs survive server restarts.
In production, integrate with Twilio, AWS SNS, or similar for SMS delivery.
"""
import random
from datetime import datetime, timedelta, timezone
from database.mongo import MongoDB


def _get_otp_collection():
    return MongoDB.get_collection('otps')


def generate_otp(phone_number):
    """
    Generate a 6-digit OTP, persist it in MongoDB, and return it.
    """
    otp = str(random.randint(100000, 999999))
    expiry_time = datetime.now(timezone.utc) + timedelta(minutes=5)

    collection = _get_otp_collection()

    # Upsert: replace any existing OTP for this phone
    collection.replace_one(
        {'phone': phone_number},
        {
            'phone': phone_number,
            'otp': otp,
            'expiry': expiry_time,
            'attempts': 0,
            'created_at': datetime.now(timezone.utc),
        },
        upsert=True,
    )

    # Log OTP for development (remove / replace with SMS in production)
    print(f"📱 OTP for {phone_number}: {otp} (expires at {expiry_time.strftime('%H:%M:%S UTC')})")

    return otp


def verify_otp(phone_number, otp_code):
    """
    Verify OTP code for a phone number.
    Returns: (success: bool, message: str)
    """
    collection = _get_otp_collection()
    otp_data = collection.find_one({'phone': phone_number})

    if not otp_data:
        return False, "No OTP found. Please request a new one."

    # Check expiry
    expiry = otp_data['expiry']
    # Make expiry timezone-aware if stored naive
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expiry:
        collection.delete_one({'phone': phone_number})
        return False, "OTP has expired. Please request a new one."

    # Check attempt limit (max 3)
    if otp_data.get('attempts', 0) >= 3:
        collection.delete_one({'phone': phone_number})
        return False, "Too many incorrect attempts. Please request a new OTP."

    # Verify OTP
    if str(otp_code) == str(otp_data['otp']):
        collection.delete_one({'phone': phone_number})
        return True, "OTP verified successfully"
    else:
        remaining = 3 - (otp_data.get('attempts', 0) + 1)
        collection.update_one(
            {'phone': phone_number},
            {'$inc': {'attempts': 1}}
        )
        return False, f"Invalid OTP. {remaining} attempt(s) remaining."


def cleanup_expired_otps():
    """
    Remove expired OTPs from MongoDB.
    Call this periodically (or use a MongoDB TTL index in production).
    """
    collection = _get_otp_collection()
    result = collection.delete_many({'expiry': {'$lt': datetime.now(timezone.utc)}})
    if result.deleted_count:
        print(f"🗑️ Cleaned up {result.deleted_count} expired OTP(s)")
