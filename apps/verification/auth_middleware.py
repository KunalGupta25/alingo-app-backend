"""
JWT Authentication Middleware
Simple JWT verification for demonstration
In production, use djangorestframework-simplejwt or similar
"""
import jwt
from django.conf import settings
from rest_framework.response import Response
from rest_framework import status
from functools import wraps


# Simple JWT secret (in production, use environment variable)
JWT_SECRET = 'your-secret-key-change-in-production'
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
    import datetime
    
    payload = {
        'user_id': str(user_id),
        'phone': phone,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7),  # 7 day expiration
        'iat': datetime.datetime.utcnow()
    }
    
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_jwt(token):
    """
    Verify JWT token and extract payload
    
    Args:
        token: JWT token string
        
    Returns:
        dict: Decoded payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def jwt_required(view_func):
    """
    Decorator to require JWT authentication on views
    
    Usage:
        @api_view(['GET'])
        @jwt_required
        def my_view(request):
            user_id = request.user_id  # Available after authentication
            ...
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Extract JWT from Authorization header
        auth_header = request.headers.get('Authorization')
        
        if not auth_header or not auth_header.startswith('Bearer '):
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Get token
        token = auth_header.split(' ')[1]
        
        # Verify token
        payload = verify_jwt(token)
        
        if not payload:
            return Response(
                {'error': 'Invalid or expired token'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Attach user info to request
        request.user_id = payload['user_id']
        request.user_phone = payload['phone']
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
