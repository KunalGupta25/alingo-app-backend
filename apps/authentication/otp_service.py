"""
OTP Service for phone number verification
Generates and verifies OTPs without external SMS provider (for development)
In production, integrate with Twilio, AWS SNS, or similar
"""
import random
import time
from datetime import datetime, timedelta

# In-memory storage for OTPs (in production, use Redis)
otp_storage = {}

def generate_otp(phone_number):
    """
    Generate a 6-digit OTP and store it with expiry
    Returns: OTP code
    """
    # Generate random 6-digit OTP
    otp = str(random.randint(100000, 999999))
    
    # Store OTP with 5-minute expiry
    expiry_time = datetime.now() + timedelta(minutes=5)
    otp_storage[phone_number] = {
        'otp': otp,
        'expiry': expiry_time,
        'attempts': 0
    }
    
    # Log OTP for development (in production, send via SMS)
    print(f"📱 OTP for {phone_number}: {otp} (expires at {expiry_time.strftime('%H:%M:%S')})")
    
    return otp

def verify_otp(phone_number, otp_code):
    """
    Verify OTP code for a phone number
    Returns: (success: bool, message: str)
    """
    # Check if OTP exists for this phone number
    if phone_number not in otp_storage:
        return False, "No OTP found. Please request a new one."
    
    otp_data = otp_storage[phone_number]
    
    # Check if OTP has expired
    if datetime.now() > otp_data['expiry']:
        del otp_storage[phone_number]
        return False, "OTP has expired. Please request a new one."
    
    # Check attempt limit (max 3 attempts)
    if otp_data['attempts'] >= 3:
        del otp_storage[phone_number]
        return False, "Too many incorrect attempts. Please request a new OTP."
    
    # Verify OTP
    if str(otp_code) == str(otp_data['otp']):
        # OTP is correct, remove from storage
        del otp_storage[phone_number]
        return True, "OTP verified successfully"
    else:
        # Increment attempt counter
        otp_data['attempts'] += 1
        return False, f"Invalid OTP. {3 - otp_data['attempts']} attempts remaining."

def cleanup_expired_otps():
    """
    Remove expired OTPs from storage
    Should be called periodically (in production, use task queue)
    """
    current_time = datetime.now()
    expired_phones = [
        phone for phone, data in otp_storage.items()
        if current_time > data['expiry']
    ]
    
    for phone in expired_phones:
        del otp_storage[phone]
    
    if expired_phones:
        print(f"🗑️ Cleaned up {len(expired_phones)} expired OTPs")
