"""
Verification API Views
Handles identity verification submission and status checking
"""
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework import status
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.conf import settings
from .services import VerificationService
from .auth_middleware import jwt_required
from database.mongo import get_users_collection
from bson import ObjectId
import os
from datetime import datetime


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
@jwt_required
def submit_verification(request):
    """
    Submit identity verification with document and face images
    
    Headers:
        Authorization: Bearer <JWT_TOKEN>
        
    Body (multipart/form-data):
        document_type: College ID | Government ID | Employee ID
        document_image: File
        face_image: File
        
    Returns:
        201: Verification submitted successfully
        400: Validation error or pending request exists
        401: Authentication required
        500: Server error
    """
    try:
        user_id = request.user_id  # From JWT middleware
        
        # Validate required fields
        document_type = request.data.get('document_type')
        document_image = request.FILES.get('document_image')
        face_image = request.FILES.get('face_image')
        
        print(f"[VERIFICATION] Submission from user {user_id}")
        print(f"[VERIFICATION] Document type: {document_type}")
        print(f"[VERIFICATION] Has document image: {document_image is not None}")
        print(f"[VERIFICATION] Has face image: {face_image is not None}")
        
        # Validate all fields present
        if not document_type or not document_image or not face_image:
            return Response(
                {'error': 'All fields are required (document_type, document_image, face_image)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate document type
        valid_types = ['College ID', 'Government ID', 'Employee ID']
        if document_type not in valid_types:
            return Response(
                {'error': f'Invalid document type. Must be one of: {", ".join(valid_types)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check for pending verification
        if VerificationService.has_pending_verification(user_id):
            return Response(
                {'error': 'You already have a pending verification request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file sizes
        if document_image.size > settings.MAX_UPLOAD_SIZE:
            return Response(
                {'error': 'Document image exceeds maximum size of 5MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if face_image.size > settings.MAX_UPLOAD_SIZE:
            return Response(
                {'error': 'Face image exceeds maximum size of 5MB'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Create media directory if it doesn't exist
        media_path = os.path.join(settings.MEDIA_ROOT, settings.VERIFICATION_UPLOAD_DIR)
        os.makedirs(media_path, exist_ok=True)
        
        # Generate unique filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        doc_filename = f"{user_id}_doc_{timestamp}.jpg"
        face_filename = f"{user_id}_face_{timestamp}.jpg"
        
        # Save images
        document_path = os.path.join(settings.VERIFICATION_UPLOAD_DIR, doc_filename)
        face_path = os.path.join(settings.VERIFICATION_UPLOAD_DIR, face_filename)
        
        doc_saved_path = default_storage.save(document_path, ContentFile(document_image.read()))
        face_saved_path = default_storage.save(face_path, ContentFile(face_image.read()))
        
        print(f"[VERIFICATION] Document saved: {doc_saved_path}")
        print(f"[VERIFICATION] Face saved: {face_saved_path}")
        
        # Create verification record
        verification = VerificationService.create_verification(
            user_id=ObjectId(user_id),
            document_type=document_type,
            document_path=doc_saved_path,
            face_path=face_saved_path
        )
        
        print(f"[VERIFICATION] Created verification record: {verification['_id']}")
        
        # Update user verification_status to PENDING
        users = get_users_collection()
        users.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {'verification_status': 'PENDING'}}
        )
        
        print(f"[VERIFICATION] Updated user status to PENDING")
        
        return Response({
            'message': 'Verification submitted successfully',
            'verification_id': str(verification['_id']),
            'status': 'PENDING'
        }, status=status.HTTP_201_CREATED)
        
    except Exception as e:
        print(f"[VERIFICATION ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': 'Failed to submit verification. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@jwt_required
def get_verification_status(request):
    """
    Get user's verification status
    
    Headers:
        Authorization: Bearer <JWT_TOKEN>
        
    Returns:
        200: Status information
        401: Authentication required
        404: User not found
        500: Server error
    """
    try:
        user_id = request.user_id
        
        print(f"[VERIFICATION] Status check for user {user_id}")
        
        # Get user from database
        users = get_users_collection()
        user = users.find_one({'_id': ObjectId(user_id)})
        
        if not user:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get verification record
        verification = VerificationService.get_user_verification(ObjectId(user_id))
        
        response_data = {
            'verification_status': user.get('verification_status', 'PENDING'),
            'has_active_request': verification is not None and verification['status'] == 'PENDING',
            'rejection_reason': None
        }
        
        # If rejected, include reason
        if verification and verification.get('status') == 'REJECTED':
            response_data['rejection_reason'] = verification.get('rejection_reason')
        
        print(f"[VERIFICATION] Status: {response_data}")
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        print(f"[VERIFICATION STATUS ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': 'Failed to check verification status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
