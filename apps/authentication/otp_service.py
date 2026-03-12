import random
import string
from datetime import datetime, timedelta
from database.mongo import MongoDB


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
        upsert=True
    )
    
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
        return True, 'OTP verified successfully'
    
    # Check if OTP exists but expired
    expired = otps.find_one({'phone': phone, 'otp': otp_code})
    if expired:
        otps.delete_one({'_id': expired['_id']})
        return False, 'OTP has expired. Please request a new one.'
    
    return False, 'Invalid OTP. Please try again.'
