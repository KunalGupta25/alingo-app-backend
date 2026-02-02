from datetime import datetime
from bson import ObjectId
import uuid
from apps.core.firebase_utils import verify_firebase_token
from database.mongo import get_users_collection


class AuthService:
    """Service layer for authentication business logic"""
    
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
            'verification_status': 'UNVERIFIED',
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
    def create_user_by_phone(phone):
        """
        Create a new user by phone number (for backend OTP flow)
        
        Args:
            phone: Phone number
            
        Returns:
            dict: Created user document
            
        Raises:
            ValueError: If user already exists
        """
        users = get_users_collection()
        
        # Check if user already exists
        existing_user = users.find_one({'phone': phone})
        
        if existing_user:
            raise ValueError("User already exists")
        
        # Generate unique user ID
        uid = str(uuid.uuid4())
        
        user_doc = {
            'uid': uid,
            'phone': phone,
            'verification_status': 'UNVERIFIED',
            'created_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
            # firebase_uid: not included for backend OTP users
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
