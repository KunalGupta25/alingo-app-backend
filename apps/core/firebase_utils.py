import firebase_admin
from firebase_admin import credentials, auth
from django.conf import settings

# Initialize Firebase Admin SDK
cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
firebase_admin.initialize_app(cred)


def verify_firebase_token(id_token):
    """
    Verify Firebase ID token and return decoded token
    
    Args:
        id_token: Firebase ID token string
        
    Returns:
        dict: Decoded token with uid, phone_number, etc.
        
    Raises:
        ValueError: If token is invalid
    """
    try:
        decoded_token = auth.verify_id_token(id_token)
        return decoded_token
    except Exception as e:
        raise ValueError(f"Invalid Firebase token: {str(e)}")
