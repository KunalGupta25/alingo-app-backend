"""
Verification Service - Handles identity verification logic
"""
from database.mongo import MongoDB
from bson import ObjectId
from datetime import datetime


class VerificationService:
    """Service for handling identity verification"""
    
    @staticmethod
    def get_collection():
        """Get verifications collection"""
        return MongoDB.get_collection('verifications')
    
    @staticmethod
    def create_verification(user_id, document_type, document_path, face_path):
        """
        Create a new verification request
        
        Args:
            user_id: ObjectId of the user
            document_type: Type of document (College ID, Government ID, Employee ID)
            document_path: Path to document image
            face_path: Path to face image
            
        Returns:
            dict: Created verification document
        """
        verification = {
            'user_id': user_id,
            'document_type': document_type,
            'document_image_url': document_path,
            'face_image_url': face_path,
            'status': 'PENDING',
            'reviewed_by': None,
            'reviewed_at': None,
            'rejection_reason': None,
            'submitted_at': datetime.utcnow(),
            'updated_at': datetime.utcnow()
        }
        
        collection = VerificationService.get_collection()
        result = collection.insert_one(verification)
        verification['_id'] = result.inserted_id
        
        return verification
    
    @staticmethod
    def has_pending_verification(user_id):
        """
        Check if user has a pending verification request
        
        Args:
            user_id: ObjectId or string of user ID
            
        Returns:
            bool: True if user has pending verification
        """
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
            
        collection = VerificationService.get_collection()
        return collection.find_one({
            'user_id': user_id,
            'status': 'PENDING'
        }) is not None
    
    @staticmethod
    def get_user_verification(user_id):
        """
        Get user's most recent verification record
        
        Args:
            user_id: ObjectId or string of user ID
            
        Returns:
            dict or None: Verification document if found
        """
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
            
        collection = VerificationService.get_collection()
        return collection.find_one(
            {'user_id': user_id},
            sort=[('submitted_at', -1)]  # Most recent first
        )
    
    @staticmethod
    def approve_verification(verification_id, admin_user_id):
        """
        Approve a verification request
        
        Args:
            verification_id: ObjectId or string of verification ID
            admin_user_id: ID of admin approving the request
            
        Returns:
            bool: True if successful
        """
        if isinstance(verification_id, str):
            verification_id = ObjectId(verification_id)
            
        collection = VerificationService.get_collection()
        result = collection.update_one(
            {'_id': verification_id},
            {'$set': {
                'status': 'APPROVED',
                'reviewed_by': admin_user_id,
                'reviewed_at': datetime.utcnow(),
                'updated_at': datetime.utcnow()
            }}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def reject_verification(verification_id, admin_user_id, reason):
        """
        Reject a verification request
        
        Args:
            verification_id: ObjectId or string of verification ID
            admin_user_id: ID of admin rejecting the request
            reason: Reason for rejection
            
        Returns:
            bool: True if successful
        """
        if isinstance(verification_id, str):
            verification_id = ObjectId(verification_id)
            
        collection = VerificationService.get_collection()
        result = collection.update_one(
            {'_id': verification_id},
            {'$set': {
                'status': 'REJECTED',
                'reviewed_by': admin_user_id,
                'reviewed_at': datetime.utcnow(),
                'rejection_reason': reason,
                'updated_at': datetime.utcnow()
            }}
        )
        
        return result.modified_count > 0
    
    @staticmethod
    def get_pending_verifications():
        """
        Get all pending verification requests
        
        Returns:
            list: List of pending verification documents
        """
        collection = VerificationService.get_collection()
        return list(collection.find({'status': 'PENDING'}).sort('submitted_at', -1))
