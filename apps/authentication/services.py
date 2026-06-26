import re
import logging
from datetime import datetime, timezone
from bson import ObjectId
import uuid
from database.mongo import get_users_collection

logger = logging.getLogger(__name__)


def _sanitize(value: str, max_len: int = 200) -> str:
    """Strip whitespace and basic HTML tags from a string input."""
    if not isinstance(value, str):
        return ''
    value = value.strip()
    value = re.sub(r'<[^>]+>', '', value)
    return value[:max_len]


class AuthService:
    """Service layer for authentication business logic"""

    @staticmethod
    def _normalize_dob(profile_data):
        """Return a stable ISO datetime string for DOB when one is provided."""
        dob_value = (profile_data or {}).get('dob')
        if not dob_value:
            return ''

        if isinstance(dob_value, datetime):
            parsed_dob = dob_value
        else:
            dob_text = str(dob_value).strip()
            if not dob_text:
                return ''

            if dob_text.endswith('Z'):
                dob_text = dob_text[:-1] + '+00:00'

            try:
                parsed_dob = datetime.fromisoformat(dob_text)
            except ValueError:
                return str(dob_value)

        if parsed_dob.tzinfo is None:
            parsed_dob = parsed_dob.replace(tzinfo=timezone.utc)

        return parsed_dob.isoformat()

    @staticmethod
    def _calculate_age_from_dob(dob_value):
        """Calculate integer age from a DOB string or datetime when possible."""
        if not dob_value:
            return ''

        if isinstance(dob_value, datetime):
            parsed_dob = dob_value
        else:
            dob_text = str(dob_value).strip()
            if not dob_text:
                return ''

            if dob_text.endswith('Z'):
                dob_text = dob_text[:-1] + '+00:00'

            try:
                parsed_dob = datetime.fromisoformat(dob_text)
            except ValueError:
                return ''

        today = datetime.now(timezone.utc).date()
        birth_date = parsed_dob.date()
        age = today.year - birth_date.year
        if (today.month, today.day) < (birth_date.month, birth_date.day):
            age -= 1

        return max(age, 0)
    
    @staticmethod
    def _format_user_response(user_doc):
        """Format user document for API response"""
        return {
            'user_id': str(user_doc['_id']),
            'uid': user_doc.get('uid', ''),
            'phone': user_doc['phone'],
            'verification_status': user_doc['verification_status'],
            'created_at': user_doc['created_at'].isoformat() if isinstance(user_doc['created_at'], datetime) else user_doc['created_at']
        }
    
    @staticmethod
    def create_user_by_phone(phone, profile_data=None):
        """
        Create a new user by phone number (for backend OTP flow)
        
        Args:
            phone: Phone number
            profile_data: Optional dict with full_name, dob, gender, bio
            
        Returns:
            dict: Created user document
            
        Raises:
            ValueError: If user already exists
        """
        users = get_users_collection()
        profile_data = profile_data or {}
        
        # Check if user already exists
        existing_user = users.find_one({'phone': phone})
        
        if existing_user:
            raise ValueError("User already exists")
        
        # Generate unique user ID
        uid = str(uuid.uuid4())
        normalized_dob = AuthService._normalize_dob(profile_data)
        derived_age = AuthService._calculate_age_from_dob(normalized_dob)
        
        now = datetime.now(timezone.utc)
        user_doc = {
            'uid': uid,
            'phone': phone,
            'firebase_uid': None,
            'created_at': now,
            'updated_at': now,
            'role': 'user',
            'rating': 0.0,
            'total_buddy_matches': 0,
            'verification_status': 'UNVERIFIED',
            'rides_completed': 0,
            'reviews_count': 0,
            'full_name': _sanitize(profile_data.get('full_name', ''), 80),
            'age': derived_age,
            'dob': normalized_dob,
            'gender': _sanitize(profile_data.get('gender', ''), 20),
            'bio': _sanitize(profile_data.get('bio', ''), 150),
        }
        
        result = users.insert_one(user_doc)
        user_doc['_id'] = result.inserted_id
        
        return AuthService._format_user_response(user_doc)
    
    @staticmethod
    def get_user_by_phone(phone):
        """
        Get user by phone number
        
        Args:
            phone: Phone number
            
        Returns:
            dict: User document or None if not found
        """
        users = get_users_collection()
        user = users.find_one({'phone': phone})
        
        if user:
            return AuthService._format_user_response(user)
        return None
