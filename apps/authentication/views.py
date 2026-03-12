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
from .otp_service import generate_otp, verify_otp


@api_view(['POST'])
def send_otp(request):
    """
    Send OTP to phone number
    Body: { "phone": "+1234567890" }
    """
    print(f"[SEND_OTP] Request received from {request.META.get('REMOTE_ADDR')}")
    try:
        phone = request.data.get('phone')
        auth_type = request.data.get('type')  # 'login' or 'signup'
        print(f"[SEND_OTP] Phone: {phone}, Type: {auth_type}")
        
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
        
        # Generate and send OTP
        otp = generate_otp(phone)
        
        # In production, send OTP via SMS here
        # Example: send_sms(phone, f"Your ALINGO verification code is: {otp}")
        
        return Response({
            'message': 'OTP sent successfully',
            'phone': phone,
            # In development, return OTP for testing
            # Remove this in production!
            'otp': otp  # For development only
        }, status=status.HTTP_200_OK)
        
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
def verify_otp_endpoint(request):
    """
    Verify OTP for phone number and login/signup user
    Body: { "phone": "+1234567890", "otp": "123456" }
    """
    print(f"[VERIFY_OTP] Request received from {request.META.get('REMOTE_ADDR')}")
    try:
        phone = request.data.get('phone')
        otp_code = request.data.get('otp')
        print(f"[VERIFY_OTP] Phone: {phone}, OTP: {otp_code}")
        
        if not phone or not otp_code:
            return Response(
                {'error': 'Phone number and OTP are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify OTP
        success, message = verify_otp(phone, otp_code)
        
        if success:
            # Check if user exists
            user = AuthService.get_user_by_phone(phone)
            
            if not user:
                # Create new user (Signup)
                print(f"Creating new user for phone: {phone}")
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
            
            return Response(user, status=status.HTTP_200_OK)
        else:
            return Response({
                'verified': False,
                'error': message
            }, status=status.HTTP_400_BAD_REQUEST)
            
    except Exception as e:
        print(f"Verify OTP Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return Response(
            {'error': str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


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
