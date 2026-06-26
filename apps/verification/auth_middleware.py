"""
JWT Authentication Middleware
Provides JWT generation and verification for API authentication.
"""
import jwt
import logging
from datetime import datetime, timedelta, timezone
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from functools import wraps

logger = logging.getLogger(__name__)

JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = 'HS256'


def generate_jwt(user_id, phone):
    """
    Generate JWT token for authenticated user
    
    Args:
        user_id: User's MongoDB ObjectId as string
        phone: User's phone number
        
    Returns:
        str: JWT token
    """
    payload = {
        'user_id': str(user_id),
        'phone': phone,
        'exp': datetime.now(timezone.utc) + timedelta(days=7),
        'iat': datetime.now(timezone.utc),
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token):
    """
    Verify JWT token and extract payload.

    Args:
        token: JWT token string

    Returns:
        dict: Decoded payload if valid AND has required fields, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        # Ensure required claims are present
        if not payload.get('user_id') or not payload.get('phone'):
            return None
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug('[JWT] Token expired')
        return None
    except jwt.InvalidTokenError as e:
        logger.debug('[JWT] Invalid token: %s', e)
        return None


def jwt_required(view_func):
    """
    Decorator to require JWT authentication on views.

    Usage:
        @api_view(['GET'])
        @jwt_required
        def my_view(request):
            user_id = request.user_id  # Available after authentication
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split(' ')[1]
        payload = verify_jwt(token)

        if not payload:
            return Response(
                {'error': 'Invalid or expired token'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        request.user_id = payload['user_id']
        request.user_phone = payload['phone']

        return view_func(request, *args, **kwargs)

    return wrapper


def verified_required(view_func):
    """
    Decorator to require both a valid JWT **and** VERIFIED status.

    Returns 403 {"error": "User not verified"} for PENDING / UNVERIFIED users.

    Usage:
        @api_view(['GET'])
        @verified_required
        def my_view(request):
            user_id = request.user_id
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # --- Step 1: validate JWT ---
        auth_header = request.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split(' ')[1]
        payload = verify_jwt(token)

        if not payload:
            return Response(
                {'error': 'Invalid or expired token'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        request.user_id = payload['user_id']
        request.user_phone = payload['phone']

        # --- Step 2: check verification status in DB ---
        from database.mongo import get_users_collection
        from bson import ObjectId

        try:
            users = get_users_collection()
            user = users.find_one({'_id': ObjectId(payload['user_id'])}, {'verification_status': 1})
        except Exception:
            return Response(
                {'error': 'Failed to validate user'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        if not user or user.get('verification_status') != 'VERIFIED':
            return Response(
                {'error': 'User not verified'},
                status=status.HTTP_403_FORBIDDEN,
            )

        return view_func(request, *args, **kwargs)

    return wrapper
