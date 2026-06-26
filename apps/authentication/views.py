"""
Authentication API Views
OTP-based authentication with rate limiting and security controls.
"""
import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.conf import settings
from database.mongo import get_users_collection
from .services import AuthService
from .otp_service import generate_otp, verify_otp
from apps.verification.auth_middleware import generate_jwt, verify_jwt

logger = logging.getLogger(__name__)


@api_view(['GET'])
def ping(request):
    """Health check endpoint"""
    return Response({'status': 'ok'})


@api_view(['POST'])
def send_otp(request):
    """
    Send OTP to phone number
    Body: { "phone": "+1234567890", "type": "login"|"signup" }
    """
    try:
        phone = request.data.get('phone')
        auth_type = request.data.get('type')  # 'login' or 'signup'
        
        if not phone:
            return Response(
                {'error': 'Phone number is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate phone format (basic validation)
        if not phone.startswith('+') or len(phone) < 10:
            return Response(
                {'error': 'Invalid phone number format. Use international format: +1234567890'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check user existence based on flow type
        users = get_users_collection()
        user_exists = users.find_one({'phone': phone}) is not None
        
        if auth_type == 'login' and not user_exists:
            return Response(
                {'error': 'No account found with this phone number. Please sign up first.'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        if auth_type == 'signup' and user_exists:
            return Response(
                {'error': 'An account with this phone number already exists. Please log in.'},
                status=status.HTTP_409_CONFLICT
            )
        
        # Generate and send OTP (may raise ValueError for rate limits)
        try:
            otp, sms_sent = generate_otp(phone)
        except ValueError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        response_data = {
            'message': 'OTP sent successfully',
            'phone': phone,
        }

        # Only include OTP in response when DEBUG=True AND SMS was not sent
        # This allows dev testing without an SMS provider
        if settings.DEBUG and not sms_sent:
            response_data['otp'] = otp

        logger.info('[SEND_OTP] Phone: %s, Type: %s, SMS sent: %s', phone[-4:], auth_type, sms_sent)
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Exception as e:
        logger.exception('[SEND_OTP ERROR] %s', e)
        return Response(
            {'error': 'Failed to send OTP. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def verify_otp_endpoint(request):
    """
    Verify OTP for phone number and login/signup user
    Body: { "phone": "+1234567890", "otp": "123456" }
    """
    try:
        phone = request.data.get('phone')
        otp_code = request.data.get('otp')
        
        if not phone or not otp_code:
            return Response(
                {'error': 'Phone number and OTP are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify OTP (includes brute-force protection)
        success, message = verify_otp(phone, otp_code)
        
        if success:
            # Check if user exists
            user = AuthService.get_user_by_phone(phone)
            
            if not user:
                # Create new user (Signup)
                logger.info('[SIGNUP] Creating new user for phone: %s', phone[-4:])
                profile_data = {
                    'full_name': request.data.get('fullName', ''),
                    'dob': request.data.get('dob', ''),
                    'gender': request.data.get('gender', ''),
                    'bio': request.data.get('bio', '')
                }
                user = AuthService.create_user_by_phone(phone, profile_data=profile_data)
            
            # Generate JWT
            from apps.verification.auth_middleware import generate_jwt
            token = generate_jwt(user['user_id'], phone)
            user['token'] = token
            
            logger.info('[VERIFY_OTP] Success for phone: %s', phone[-4:])
            return Response(user, status=status.HTTP_200_OK)
        else:
            return Response({
                'verified': False,
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        logger.exception('[VERIFY_OTP ERROR] %s', e)
        return Response(
            {'error': 'Verification failed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def refresh_token(request):
    """
    POST /auth/token/refresh
    Body: { "token": "<existing_jwt>" }

    Issues a new JWT with a fresh 7-day expiry.
    Use this when the app resumes and wants to silently extend the session
    before the current token expires.

    Returns 401 if the token is already expired or invalid.
    """
    try:
        old_token = request.data.get('token')
        if not old_token:
            return Response({'error': 'token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        payload = verify_jwt(old_token)
        if not payload:
            return Response(
                {'error': 'Token is invalid or expired. Please log in again.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Verify user still exists
        from bson import ObjectId
        users = get_users_collection()
        user = users.find_one(
            {'_id': ObjectId(payload['user_id'])},
            {'phone': 1, 'verification_status': 1},
        )
        if not user:
            return Response(
                {'error': 'User not found.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        new_token = generate_jwt(payload['user_id'], payload['phone'])
        logger.info('[TOKEN_REFRESH] Issued new token for user %s', payload['user_id'])

        return Response({
            'token': new_token,
            'verification_status': user.get('verification_status', 'UNVERIFIED'),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[TOKEN_REFRESH ERROR] %s', e)
        return Response({'error': 'Failed to refresh token.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

