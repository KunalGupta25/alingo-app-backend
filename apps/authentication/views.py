from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from .services import AuthService
from .otp_service import generate_otp, verify_otp


@api_view(['GET'])
def ping(request):
    """Health check endpoint"""
    print(f"[PING] Request received from {request.META.get('REMOTE_ADDR')}")
    return Response({'status': 'ok'})

@api_view(['POST'])
def send_otp(request):
    """
    Send OTP to phone number
    Body: { "phone": "+1234567890" }
    """
    print(f"[SEND_OTP] Request received from {request.META.get('REMOTE_ADDR')}")
    try:
        phone = request.data.get('phone')
        print(f"[SEND_OTP] Phone: {phone}")
        
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
                user = AuthService.create_user_by_phone(phone)
            
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
    Register a new user
    
    Supports two authentication methods:
    1. Firebase token (legacy): { "firebase_token": "..." }
    2. Backend OTP verified token: { "firebase_token": "verified_+1234567890_..." }
    """
    try:
        firebase_token = request.data.get('firebase_token')
        
        print(f"Signup request received with token: {firebase_token[:30] if firebase_token else 'None'}...")
        
        if not firebase_token:
            return Response(
                {'error': 'firebase_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if this is a backend OTP verified token
        if firebase_token.startswith('verified_'):
            # Extract phone from token: verified_+1234567890_timestamp
            parts = firebase_token.split('_')
            print(f"Token parts: {parts}")
            
            if len(parts) >= 2:
                phone = parts[1]
                print(f"Extracted phone: {phone}")
                # Create user by phone
                user = AuthService.create_user_by_phone(phone)
                print(f"User created successfully: {user}")
                
                # Generate JWT token
                from apps.verification.auth_middleware import generate_jwt
                token = generate_jwt(user['user_id'], phone)
                
                # Add token to response
                user['token'] = token
                
                return Response(user, status=status.HTTP_201_CREATED)
            else:
                print(f"Invalid token format, parts length: {len(parts)}")
                return Response(
                    {'error': 'Invalid verification token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Firebase flow
            user_info = AuthService.verify_and_extract_user_info(firebase_token)
            user = AuthService.create_user(
                firebase_uid=user_info['firebase_uid'],
                phone=user_info['phone']
            )
            
            # Generate JWT token
            from apps.verification.auth_middleware import generate_jwt
            token = generate_jwt(user['user_id'], user_info['phone'])
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
    Login existing user
    
    Supports two authentication methods:
    1. Firebase token (legacy): { "firebase_token": "..." }
    2. Backend OTP verified token: { "firebase_token": "verified_+1234567890_..." }
    """
    try:
        firebase_token = request.data.get('firebase_token')
        
        if not firebase_token:
            return Response(
                {'error': 'firebase_token is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if this is a backend OTP verified token
        if firebase_token.startswith('verified_'):
            # Extract phone from token: verified_+1234567890_timestamp
            parts = firebase_token.split('_')
            if len(parts) >= 2:
                phone = parts[1]
                # Get user by phone
                user = AuthService.get_user_by_phone(phone)
                
                if not user:
                    return Response(
                        {'error': 'User not found. Please sign up first.'},
                        status=status.HTTP_404_NOT_FOUND
                    )
                
                # Generate JWT token
                from apps.verification.auth_middleware import generate_jwt
                token = generate_jwt(user['user_id'], phone)
                user['token'] = token
                
                return Response(user, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': 'Invalid verification token'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        else:
            # Firebase flow
            user_info = AuthService.verify_and_extract_user_info(firebase_token)
            user = AuthService.get_user_by_firebase_uid(user_info['firebase_uid'])
            
            if not user:
                return Response(
                    {'error': 'User not found. Please sign up first.'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Generate JWT token
            from apps.verification.auth_middleware import generate_jwt
            token = generate_jwt(user['user_id'], user_info['phone'])
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
