from datetime import datetime, timezone
from bson import ObjectId
import uuid
from apps.core.firebase_utils import verify_firebase_token
from database.mongo import get_users_collection


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
    def verify_and_extract_user_info(firebase_token):
        """
        Verify Firebase token and extract user information
        
        Args:
            firebase_token: Firebase ID token string
            
        Returns:
            dict: User info with firebase_uid and phone
            
        Raises:
            ValueError: If token is invalid or missing phone number
        """
        decoded_token = verify_firebase_token(firebase_token)
        
        firebase_uid = decoded_token.get('uid')
        phone = decoded_token.get('phone_number')
        
        if not phone:
            raise ValueError("Phone number not found in Firebase token")
        
        return {
            'firebase_uid': firebase_uid,
            'phone': phone
        }
    
    @staticmethod
    def create_user(firebase_uid, phone):
        """
        Create a new user in MongoDB
        
        Args:
            firebase_uid: Firebase UID
            phone: Phone number
            
        Returns:
            dict: Created user document
            
        Raises:
            ValueError: If user already exists
        """
        users = get_users_collection()
        
        # Check if user already exists
        existing_user = users.find_one({
            '$or': [
                {'firebase_uid': firebase_uid},
                {'phone': phone}
            ]
        })
        
        if existing_user:
            raise ValueError("User already exists")
        
        # Create new user
        user_doc = {
            'firebase_uid': firebase_uid,
            'phone': phone,
            'full_name': '',
            'verification_status': 'UNVERIFIED',
            'rating': 0.0,
            'total_buddy_matches': 0,
            'available_for_ride': False,
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        result = users.insert_one(user_doc)
        user_doc['_id'] = result.inserted_id
        
        return AuthService._format_user_response(user_doc)
    
    @staticmethod
    def get_user_by_firebase_uid(firebase_uid):
        """
        Get user by Firebase UID
        
        Args:
            firebase_uid: Firebase UID
            
        Returns:
            dict: User document or None if not found
        """
        users = get_users_collection()
        user = users.find_one({'firebase_uid': firebase_uid})
        
        if user:
            return AuthService._format_user_response(user)
        return None
    
    @staticmethod
    def _format_user_response(user_doc):
        """Format user document for API response"""
        return {
            'user_id': str(user_doc['_id']),
            'uid': user_doc.get('uid', user_doc.get('firebase_uid', '')),  # Support both old and new schema
            'firebase_uid': user_doc.get('firebase_uid', ''),
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
        
        user_doc = {
            'uid': uid,
            'phone': phone,
            'firebase_uid': None, # explicitly None for phone auth
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
            'role': 'user',
            'rating': 0.0,
            'total_buddy_matches': 0,
            'verification_status': 'UNVERIFIED',
            'rides_completed': 0,
            'reviews_count': 0,
            'full_name': profile_data.get('full_name', ''),
            'age': derived_age,
            'dob': normalized_dob,
            'gender': profile_data.get('gender', ''),
            'bio': profile_data.get('bio', '')
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
