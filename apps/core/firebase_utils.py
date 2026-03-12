import json
import os
import firebase_admin
from firebase_admin import credentials, auth
from django.conf import settings


def _get_firebase_credentials():
    """
    Load Firebase credentials from either:
    1. FIREBASE_CREDENTIALS_JSON env var (raw JSON string — for Railway/cloud)
    2. FIREBASE_CREDENTIALS_PATH setting (file path — for local dev)
    """
    # Priority 1: Raw JSON string from environment (Railway deployment)
    json_str = os.getenv('FIREBASE_CREDENTIALS_JSON')
    if json_str:
        try:
            cred_dict = json.loads(json_str)
            return credentials.Certificate(cred_dict)
        except (json.JSONDecodeError, ValueError) as e:
            raise ValueError(f"FIREBASE_CREDENTIALS_JSON is set but contains invalid JSON: {e}")

    # Priority 2: File path from settings
    cred_path = getattr(settings, 'FIREBASE_CREDENTIALS_PATH', None)
    if cred_path:
        # Check if the value looks like JSON content (starts with '{') rather than a file path
        if isinstance(cred_path, str) and cred_path.strip().startswith('{'):
            try:
                cred_dict = json.loads(cred_path)
                return credentials.Certificate(cred_dict)
            except (json.JSONDecodeError, ValueError) as e:
                raise ValueError(f"FIREBASE_CREDENTIALS_PATH contains JSON but it's invalid: {e}")
        # Otherwise treat as a file path
        if os.path.exists(cred_path):
            return credentials.Certificate(cred_path)
        else:
            raise FileNotFoundError(
                f"Firebase credentials file not found at: {cred_path}. "
                f"Set FIREBASE_CREDENTIALS_JSON env var with the JSON content for cloud deployment."
            )

    raise ValueError(
        "No Firebase credentials configured. Set either "
        "FIREBASE_CREDENTIALS_JSON (JSON string) or FIREBASE_CREDENTIALS_PATH (file path)."
    )


# Initialize Firebase Admin SDK
if not firebase_admin._apps:
    cred = _get_firebase_credentials()
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
