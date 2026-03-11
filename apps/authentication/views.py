from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from database.mongo import get_users_collection
from .services import AuthService


@api_view(['GET'])
def ping(request):
    """Health check endpoint"""
    print(f"[PING] Request received from {request.META.get('REMOTE_ADDR')}")
    return Response({'status': 'ok'})


@api_view(['POST'])
def signup(request):
    """
    Register a new user using Firebase Phone Auth
    Body: { "firebase_token": "...", "fullName": "...", "dob": "...", "gender": "...", "bio": "..." }
    """
    try:
        firebase_token = request.data.get('firebase_token')
        
        print(f"Signup request received with token: {firebase_token[:30] if firebase_token else 'None'}...")
        
        if not firebase_token:
            return Response(
                {'error': 'firebase_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify Firebase Token
        user_info = AuthService.verify_and_extract_user_info(firebase_token)
        phone = user_info['phone']
        
        # Extract profile data
        profile_data = {
            'full_name': request.data.get('fullName', ''),
            'dob': request.data.get('dob', ''),
            'gender': request.data.get('gender', ''),
            'bio': request.data.get('bio', '')
        }
        
        # Check if user exists before creating
        existing = AuthService.get_user_by_phone(phone)
        if existing:
            return Response(
                {'error': 'An account with this phone number already exists. Please login instead.'},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        print(f"Creating new user for phone: {phone}")
        # Create user by phone (which mimics our previous verified approach but now guaranteed by Firebase)
        # Note: We are using create_user_by_phone instead of create_user to pass complete profile data
        user = AuthService.create_user_by_phone(phone, profile_data=profile_data)
        
        # We need to manually link the firebase UID since create_user_by_phone sets it to None
        users_col = get_users_collection()
        users_col.update_one(
            {'phone': phone},
            {'$set': {'firebase_uid': user_info['firebase_uid']}}
        )
        user['firebase_uid'] = user_info['firebase_uid']
        
        # Generate JWT token
        from apps.verification.auth_middleware import generate_jwt
        token = generate_jwt(user['user_id'], phone)
        user['token'] = token
        
        return Response(user, status=status.HTTP_201_CREATED)
        
    except ValueError as e:
        print(f"ValueError during signup: {str(e)}")
        
        # Provide user-friendly error messages
        error_message = str(e)
        if "already exists" in error_message.lower():
            error_message = "An account with this phone number already exists. Please login instead."
        
        return Response(
            {'error': error_message},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        print(f"Signup error: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': 'Unable to create account. Please try again later.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
def login(request):
    """
    Login existing user using Firebase Phone Auth
    Body: { "firebase_token": "..." }
    """
    try:
        firebase_token = request.data.get('firebase_token')
        
        if not firebase_token:
            return Response(
                {'error': 'firebase_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify Firebase token
        user_info = AuthService.verify_and_extract_user_info(firebase_token)
        phone = user_info['phone']
        
        # Get user by phone
        user = AuthService.get_user_by_phone(phone)
        
        if not user:
            return Response(
                {'error': 'User not found. Please sign up first.'},
                status=status.HTTP_404_NOT_FOUND
            )
            
        # Optional: ensure firebase_uid is linked in case of legacy records
        if not user.get('firebase_uid'):
            users_col = get_users_collection()
            users_col.update_one(
                {'phone': phone},
                {'$set': {'firebase_uid': user_info['firebase_uid']}}
            )
        
        # Generate JWT token
        from apps.verification.auth_middleware import generate_jwt
        token = generate_jwt(user['user_id'], phone)
        user['token'] = token
        
        return Response(user, status=status.HTTP_200_OK)
        
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        print(f"Login error: {str(e)}")
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
