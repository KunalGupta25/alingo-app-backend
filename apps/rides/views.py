"""
Rides API Views — Block 5 + Block 6
POST /rides/create   →  verified_required
POST /rides/search   →  verified_required
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import date, datetime
from bson import ObjectId

from apps.verification.auth_middleware import verified_required
from database.mongo import get_users_collection
from .services import RideService


# ─────────────────────────────────────────────────────────
# BLOCK 5 — Create Ride
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def create_ride(request):
    """
    POST /rides/create

    Body: { destination, ride_date, ride_time, max_seats, route_polyline }
    Returns: 201 { ride_id, status, destination, ride_date, ride_time, max_seats }
    """
    try:
        user_id = request.user_id

        users = get_users_collection()
        user  = users.find_one({'_id': ObjectId(user_id)})

        if not user:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        if not user.get('available_for_ride', False):
            return Response(
                {'error': 'You must set yourself as available for rides before creating one.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        start_location = user.get('location')
        if not start_location:
            return Response(
                {'error': 'Your location is not set. Open the Home screen to share your location first.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if RideService.get_active_ride_for_user(user_id):
            return Response(
                {'error': 'You already have an active ride. Cancel it before creating a new one.'},
                status=status.HTTP_409_CONFLICT,
            )

        destination    = request.data.get('destination')
        ride_date_str  = request.data.get('ride_date')
        ride_time      = request.data.get('ride_time')
        max_seats      = request.data.get('max_seats')
        route_polyline = request.data.get('route_polyline', '')

        if not destination or not ride_date_str or not ride_time or max_seats is None:
            return Response(
                {'error': 'destination, ride_date, ride_time, and max_seats are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(destination, dict) or 'name' not in destination or 'coordinates' not in destination:
            return Response(
                {'error': 'destination must be { name, coordinates: [lng, lat] }'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            max_seats = int(max_seats)
        except (ValueError, TypeError):
            return Response({'error': 'max_seats must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        if not (1 <= max_seats <= 4):
            return Response({'error': 'max_seats must be between 1 and 4.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride_date = datetime.strptime(ride_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'ride_date must be YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        if ride_date < date.today():
            return Response({'error': 'Ride date cannot be in the past.'}, status=status.HTTP_400_BAD_REQUEST)

        ride = RideService.create_ride(
            creator_id=user_id,
            start_location=start_location,
            destination=destination,
            ride_date=ride_date_str,
            ride_time=ride_time,
            max_seats=max_seats,
            route_polyline=route_polyline,
        )

        print(f'[RIDE_CREATE] User {user_id} → {destination["name"]} on {ride_date_str}')
        return Response({
            'ride_id':     str(ride['_id']),
            'status':      ride['status'],
            'destination': ride['destination']['name'],
            'ride_date':   ride['ride_date'],
            'ride_time':   ride['ride_time'],
            'max_seats':   ride['max_seats'],
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        print(f'[RIDE_CREATE ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to create ride.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 6 — Search Rides (Find Buddy)
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def search_rides(request):
    """
    POST /rides/search

    Body:
    {
        "user_location":  [longitude, latitude],
        "ride_date":      "YYYY-MM-DD",
        "route_polyline": "encoded_string"   (optional)
    }

    Returns: [ { ride_id, creator_name, creator_rating, distance_meters,
                 available_seats, ride_time, destination_name } ]
    """
    try:
        user_id = request.user_id

        user_location  = request.data.get('user_location')
        ride_date_str  = request.data.get('ride_date')
        route_polyline = request.data.get('route_polyline', '')

        # ── Validate ─────────────────────────────────────
        if not user_location or not ride_date_str:
            return Response(
                {'error': 'user_location and ride_date are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not isinstance(user_location, list) or len(user_location) != 2:
            return Response(
                {'error': 'user_location must be [longitude, latitude].'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            ride_date = datetime.strptime(ride_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'error': 'ride_date must be YYYY-MM-DD.'}, status=status.HTTP_400_BAD_REQUEST)

        if ride_date < date.today():
            return Response({'error': 'ride_date cannot be in the past.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Run matching pipeline ─────────────────────────
        matches = RideService.search_rides(
            user_id       = user_id,
            user_location = [float(user_location[0]), float(user_location[1])],
            ride_date     = ride_date_str,
            user_polyline = route_polyline,
        )

        return Response(matches, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[RIDE_SEARCH ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Search failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
