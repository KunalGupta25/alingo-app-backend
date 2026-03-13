import random
import string
from datetime import datetime, timedelta
from database.mongo import MongoDB


def _log_otp_event(phone, otp_code, action, status):
    """Log OTP events (generation, verification) to MongoDB"""
    logs = MongoDB.get_collection('otp_logs')
    logs.insert_one({
        'phone': phone,
        'otp': otp_code,
        'action': action,
        'status': status,
        'timestamp': datetime.utcnow()
    })
def generate_otp(phone):
    """
    Generate a 6-digit OTP and store it in MongoDB with TTL expiry.
    
    Args:
        phone: Phone number to generate OTP for
        
    Returns:
        str: The generated OTP code
    """
    otp_code = ''.join(random.choices(string.digits, k=6))
    
    otps = MongoDB.get_collection('otps')
    
    # Upsert: replace any existing OTP for this phone
    otps.update_one(
        {'phone': phone},
        {
            '$set': {
                'phone': phone,
                'otp': otp_code,
                'expiry': datetime.utcnow() + timedelta(minutes=5),
                'created_at': datetime.utcnow(),
            }
        },
        upsert=True,
    )
    
    # Log generation
    _log_otp_event(phone, otp_code, 'SEND', 'SUCCESS')
    
    return otp_code


def verify_otp(phone, otp_code):
    """
    Verify an OTP code for a given phone number.
    
    Args:
        phone: Phone number
        otp_code: OTP code to verify
        
    Returns:
        tuple: (success: bool, message: str)
    """
    otps = MongoDB.get_collection('otps')
    
    record = otps.find_one({
        'phone': phone,
        'otp': otp_code,
        'expiry': {'$gt': datetime.utcnow()}
    })
    
    if record:
        # Delete used OTP
        otps.delete_one({'_id': record['_id']})
        _log_otp_event(phone, otp_code, 'VERIFY', 'SUCCESS')
        return True, 'OTP verified successfully'
    
    # Check if OTP exists but expired
    expired = otps.find_one({'phone': phone, 'otp': otp_code})
    if expired:
        otps.delete_one({'_id': expired['_id']})
        _log_otp_event(phone, otp_code, 'VERIFY', 'EXPIRED')
        return False, 'OTP has expired. Please request a new one.'
    
    _log_otp_event(phone, otp_code, 'VERIFY', 'FAILED')
    return False, 'Invalid OTP. Please try again.'
