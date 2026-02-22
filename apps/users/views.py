"""
Users API Views — Block 4: Home Screen
All endpoints require VERIFIED status (via verified_required decorator).
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from apps.verification.auth_middleware import verified_required
from database.mongo import get_users_collection
from bson import ObjectId
from datetime import datetime


@api_view(['GET'])
@verified_required
def get_me(request):
    """
    GET /users/me
    Returns the current user's profile summary for the Home screen.

    Headers:
        Authorization: Bearer <JWT_TOKEN>

    Returns:
        200: {
            "user_id", "phone", "full_name", "rating",
            "total_buddy_matches", "available_for_ride", "verification_status"
        }
    """
    try:
        users = get_users_collection()
        user = users.find_one({'_id': ObjectId(request.user_id)})

        if not user:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'user_id': str(user['_id']),
            'phone': user.get('phone', ''),
            'full_name': user.get('full_name', ''),
            'rating': user.get('rating', 0.0),
            'total_buddy_matches': user.get('total_buddy_matches', 0),
            'available_for_ride': user.get('available_for_ride', False),
            'verification_status': user.get('verification_status', 'PENDING'),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[GET_ME ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to fetch user'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@verified_required
def update_availability(request):
    """
    PATCH /users/availability
    Toggle the user's ride availability.

    Headers:
        Authorization: Bearer <JWT_TOKEN>

    Body:
        { "available_for_ride": true | false }

    Returns:
        200: { "available_for_ride": true }
        400: Missing / invalid field
    """
    try:
        available = request.data.get('available_for_ride')

        if available is None:
            return Response(
                {'error': 'available_for_ride is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(available, bool):
            return Response(
                {'error': 'available_for_ride must be a boolean'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        users = get_users_collection()
        users.update_one(
            {'_id': ObjectId(request.user_id)},
            {'$set': {'available_for_ride': available, 'updated_at': datetime.utcnow()}},
        )

        print(f'[AVAILABILITY] User {request.user_id} → available_for_ride={available}')
        return Response({'available_for_ride': available}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[AVAILABILITY ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to update availability'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['PATCH'])
@verified_required
def update_location(request):
    """
    PATCH /users/location
    Store the user's current GeoJSON location (prepares for Block 6 ride matching).

    Headers:
        Authorization: Bearer <JWT_TOKEN>

    Body:
        { "latitude": 12.9716, "longitude": 77.5946 }

    Returns:
        200: { "message": "Location updated" }
        400: Missing fields
    """
    try:
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')

        if latitude is None or longitude is None:
            return Response(
                {'error': 'latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        geo_point = {
            'type': 'Point',
            'coordinates': [float(longitude), float(latitude)],  # GeoJSON: [lng, lat]
        }

        users = get_users_collection()
        users.update_one(
            {'_id': ObjectId(request.user_id)},
            {'$set': {'location': geo_point, 'updated_at': datetime.utcnow()}},
        )

        print(f'[LOCATION] User {request.user_id} → ({latitude}, {longitude})')
        return Response({'message': 'Location updated'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[LOCATION ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to update location'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
