"""
OTP Service — Generation, verification, SMS delivery, and brute-force protection.

SMS Provider:
    Set SMS_PROVIDER env var to 'twilio' to enable real SMS delivery.
    Default: 'dev' — OTP logged to console, returned in response (DEBUG only).
"""
import os
import random
import string
import logging
from datetime import datetime, timedelta, timezone
from database.mongo import MongoDB

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────
SMS_PROVIDER = os.getenv('SMS_PROVIDER', 'dev')  # 'dev' | 'twilio'
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID', '')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN', '')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER', '')

# Brute-force limits
MAX_VERIFY_ATTEMPTS = 5       # per OTP record
MAX_SEND_PER_PHONE = 5        # per phone per hour
LOCKOUT_MINUTES = 30           # lockout duration after max failures


def _log_otp_event(phone, otp_code, action, status):
    """Log OTP events (generation, verification) to MongoDB"""
    logs = MongoDB.get_collection('otp_logs')
    logs.insert_one({
        'phone': phone,
        'otp': otp_code,
        'action': action,
        'status': status,
        'timestamp': datetime.now(timezone.utc),
    })


def _send_sms(phone, otp_code):
    """
    Send OTP via configured SMS provider.
    Returns True if sent, False if dev mode (not sent).
    """
    if SMS_PROVIDER == 'twilio':
        try:
            from twilio.rest import Client
            client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=f'Your ALINGO verification code is: {otp_code}. Valid for 5 minutes.',
                from_=TWILIO_PHONE_NUMBER,
                to=phone,
            )
            logger.info('[SMS] OTP sent via Twilio to %s', phone[-4:])
            return True
        except ImportError:
            logger.error('[SMS] Twilio package not installed. Run: pip install twilio')
            return False
        except Exception as e:
            logger.error('[SMS] Twilio send failed: %s', e)
            return False

    # Dev mode — OTP not sent via SMS
    logger.info('[SMS_DEV] OTP for %s: %s (not sent — dev mode)', phone[-4:], otp_code)
    return False


def _is_phone_locked(phone):
    """Check if phone is locked out due to too many failed attempts."""
    otps = MongoDB.get_collection('otps')
    record = otps.find_one({'phone': phone})
    if not record:
        return False

    if record.get('locked_until'):
        locked_until = record['locked_until']
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            return True
        # Lockout expired — clear it
        otps.update_one(
            {'phone': phone},
            {'$unset': {'locked_until': '', 'verify_attempts': ''}},
        )
    return False


def _check_send_rate(phone):
    """Check if phone has exceeded send rate limit (MAX_SEND_PER_PHONE per hour)."""
    logs = MongoDB.get_collection('otp_logs')
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    count = logs.count_documents({
        'phone': phone,
        'action': 'SEND',
        'timestamp': {'$gt': one_hour_ago},
    })
    return count < MAX_SEND_PER_PHONE


def generate_otp(phone):
    """
    Generate a 6-digit OTP and store it in MongoDB with TTL expiry.
    
    Args:
        phone: Phone number to generate OTP for
        
    Returns:
        tuple: (otp_code: str, sms_sent: bool)
        
    Raises:
        ValueError: If phone is rate-limited or locked out
    """
    # Check lockout
    if _is_phone_locked(phone):
        raise ValueError(f'Too many failed attempts. Try again in {LOCKOUT_MINUTES} minutes.')

    # Check send rate
    if not _check_send_rate(phone):
        raise ValueError(f'Too many OTP requests. Maximum {MAX_SEND_PER_PHONE} per hour.')

    otp_code = ''.join(random.choices(string.digits, k=6))
    
    otps = MongoDB.get_collection('otps')
    
    # Upsert: replace any existing OTP for this phone, reset attempts
    otps.update_one(
        {'phone': phone},
        {
            '$set': {
                'phone': phone,
                'otp': otp_code,
                'expiry': datetime.now(timezone.utc) + timedelta(minutes=5),
                'created_at': datetime.now(timezone.utc),
                'verify_attempts': 0,
            },
            '$unset': {'locked_until': ''},
        },
        upsert=True,
    )
    
    # Send via configured provider
    sms_sent = _send_sms(phone, otp_code)
    
    # Log generation
    _log_otp_event(phone, otp_code, 'SEND', 'SUCCESS')
    
    return otp_code, sms_sent


def verify_otp(phone, otp_code):
    """
    Verify an OTP code for a given phone number.
    Includes brute-force protection with attempt counting and lockout.
    
    Args:
        phone: Phone number
        otp_code: OTP code to verify
        
    Returns:
        tuple: (success: bool, message: str)
    """
    otps = MongoDB.get_collection('otps')

    # Check lockout first
    if _is_phone_locked(phone):
        return False, f'Account temporarily locked. Try again in {LOCKOUT_MINUTES} minutes.'

    # Find OTP record for this phone
    record = otps.find_one({'phone': phone})

    if not record:
        _log_otp_event(phone, otp_code, 'VERIFY', 'NO_RECORD')
        return False, 'No OTP found. Please request a new one.'

    # Check attempts
    attempts = record.get('verify_attempts', 0)
    if attempts >= MAX_VERIFY_ATTEMPTS:
        # Lock the phone
        otps.update_one(
            {'phone': phone},
            {'$set': {'locked_until': datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_MINUTES)}},
        )
        _log_otp_event(phone, otp_code, 'VERIFY', 'LOCKED')
        return False, f'Too many failed attempts. Account locked for {LOCKOUT_MINUTES} minutes.'

    # Increment attempt counter
    otps.update_one(
        {'phone': phone},
        {'$inc': {'verify_attempts': 1}},
    )

    # Check expiry — handle both naive and aware datetimes (mongomock returns naive)
    expiry = record.get('expiry')
    if expiry:
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        if expiry < datetime.now(timezone.utc):
            otps.delete_one({'_id': record['_id']})
            _log_otp_event(phone, otp_code, 'VERIFY', 'EXPIRED')
            return False, 'OTP has expired. Please request a new one.'

    # Check code match
    if record.get('otp') == otp_code:
        # Success — delete used OTP
        otps.delete_one({'_id': record['_id']})
        _log_otp_event(phone, otp_code, 'VERIFY', 'SUCCESS')
        return True, 'OTP verified successfully'

    remaining = MAX_VERIFY_ATTEMPTS - attempts - 1
    _log_otp_event(phone, otp_code, 'VERIFY', 'FAILED')
    return False, f'Invalid OTP. {remaining} attempt(s) remaining.'
