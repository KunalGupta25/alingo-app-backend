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


# ─────────────────────────────────────────────────────────
# BLOCK 7 — Request to Join
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def request_ride(request):
    """
    POST /rides/request
    Body: { "ride_id": "<ObjectId>" }

    Rules:
    - Ride must be ACTIVE
    - Caller cannot be the creator
    - Caller not already a participant (any status)
    - Approved seats < max_seats
    Adds participant with status=PENDING.
    """
    try:
        user_id = request.user_id
        ride_id_str = request.data.get('ride_id')

        if not ride_id_str:
            return Response({'error': 'ride_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride_oid = ObjectId(ride_id_str)
            user_oid = ObjectId(user_id)
        except Exception:
            return Response({'error': 'Invalid ride_id.'}, status=status.HTTP_400_BAD_REQUEST)

        rides = get_rides_collection()
        ride  = rides.find_one({'_id': ride_oid})

        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Must be ACTIVE
        if ride.get('status') != 'ACTIVE':
            return Response({'error': 'This ride is no longer active.'}, status=status.HTTP_400_BAD_REQUEST)

        # Cannot request own ride
        if ride['creator_id'] == user_oid:
            return Response({'error': 'You cannot request to join your own ride.'}, status=status.HTTP_400_BAD_REQUEST)

        participants = ride.get('participants', [])

        # Already a participant (any status)
        already = next((p for p in participants if p.get('user_id') == user_oid), None)
        if already:
            existing_status = already.get('status', '')
            if existing_status == 'PENDING':
                return Response({'error': 'Your request is already pending.'}, status=status.HTTP_409_CONFLICT)
            if existing_status == 'APPROVED':
                return Response({'error': 'You are already in this ride.'}, status=status.HTTP_409_CONFLICT)
            if existing_status == 'REJECTED':
                return Response({'error': 'Your request was rejected by the creator.'}, status=status.HTTP_409_CONFLICT)

        # Seat check — count only APPROVED participants
        approved_count = sum(1 for p in participants if p.get('status') == 'APPROVED')
        if approved_count >= ride.get('max_seats', 1):
            return Response({'error': 'This ride is full.'}, status=status.HTTP_400_BAD_REQUEST)

        # Atomic push
        rides.update_one(
            {'_id': ride_oid},
            {'$push': {'participants': {'user_id': user_oid, 'status': 'PENDING'}}},
        )

        print(f'[RIDE_REQUEST] User {user_id} → ride {ride_id_str}')
        return Response({'message': 'Request sent'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[RIDE_REQUEST ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to send request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 7 — Creator Responds (Approve / Reject)
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def respond_ride(request):
    """
    POST /rides/respond
    Body: { "ride_id": "<ObjectId>", "user_id": "<ObjectId>", "action": "APPROVE"|"REJECT" }

    Rules:
    - Only the ride creator can call this
    - Ride must be ACTIVE
    - Target participant must exist
    - APPROVE: re-check seat count (avoid race conditions)
    - Uses positional $ operator for atomic participant update
    """
    try:
        caller_id   = request.user_id
        ride_id_str = request.data.get('ride_id')
        target_id_str = request.data.get('user_id')
        action      = request.data.get('action', '').upper()

        if not ride_id_str or not target_id_str or not action:
            return Response(
                {'error': 'ride_id, user_id, and action are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action not in ('APPROVE', 'REJECT'):
            return Response({'error': 'action must be APPROVE or REJECT.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride_oid   = ObjectId(ride_id_str)
            target_oid = ObjectId(target_id_str)
            caller_oid = ObjectId(caller_id)
        except Exception:
            return Response({'error': 'Invalid ObjectId.'}, status=status.HTTP_400_BAD_REQUEST)

        rides = get_rides_collection()
        ride  = rides.find_one({'_id': ride_oid})

        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        # Only creator
        if ride['creator_id'] != caller_oid:
            return Response({'error': 'Only the ride creator can respond to requests.'}, status=status.HTTP_403_FORBIDDEN)

        # Must be ACTIVE
        if ride.get('status') != 'ACTIVE':
            return Response({'error': 'Cannot respond after the ride is completed or cancelled.'}, status=status.HTTP_400_BAD_REQUEST)

        participants = ride.get('participants', [])

        # Find target participant
        target = next((p for p in participants if p.get('user_id') == target_oid), None)
        if not target:
            return Response({'error': 'User has not requested to join this ride.'}, status=status.HTTP_404_NOT_FOUND)

        if target.get('status') != 'PENDING':
            return Response(
                {'error': f'Request is already {target["status"].lower()}.'},
                status=status.HTTP_409_CONFLICT,
            )

        if action == 'APPROVE':
            # Re-check seats (prevent race conditions)
            approved_count = sum(1 for p in participants if p.get('status') == 'APPROVED')
            if approved_count >= ride.get('max_seats', 1):
                return Response({'error': 'Ride is full. Cannot approve more riders.'}, status=status.HTTP_400_BAD_REQUEST)

        new_status = 'APPROVED' if action == 'APPROVE' else 'REJECTED'

        # Atomic positional update
        result = rides.update_one(
            {'_id': ride_oid, 'participants.user_id': target_oid},
            {'$set': {'participants.$.status': new_status}},
        )

        if result.modified_count == 0:
            return Response({'error': 'Update failed. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        msg = 'User approved' if action == 'APPROVE' else 'User rejected'
        print(f'[RIDE_RESPOND] Creator {caller_id} → {action} user {target_id_str} on ride {ride_id_str}')
        return Response({'message': msg}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[RIDE_RESPOND ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to respond.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 8 — Complete Ride (Majority Vote)
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def complete_ride(request):
    """
    POST /rides/complete
    Body: { "ride_id": "<ObjectId>" }

    Majority vote logic:
    - eligible = creator + all APPROVED participants
    - majority_needed = floor(len(eligible) / 2) + 1
    - Adds caller to completion_votes ($addToSet, idempotent)
    - If votes >= majority_needed → COMPLETED + timestamp
    - On completion: increments total_buddy_matches for all eligible users
    """
    try:
        caller_id   = request.user_id
        ride_id_str = request.data.get('ride_id')

        if not ride_id_str:
            return Response({'error': 'ride_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride_oid   = ObjectId(ride_id_str)
            caller_oid = ObjectId(caller_id)
        except Exception:
            return Response({'error': 'Invalid ride_id.'}, status=status.HTTP_400_BAD_REQUEST)

        rides = get_rides_collection()
        ride  = rides.find_one({'_id': ride_oid})

        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        if ride.get('status') != 'ACTIVE':
            return Response({'error': 'Ride is not active.'}, status=status.HTTP_400_BAD_REQUEST)

        # Build eligible set: creator + APPROVED participants
        participants = ride.get('participants', [])
        approved_ids = [p['user_id'] for p in participants if p.get('status') == 'APPROVED']
        creator_oid  = ride['creator_id']
        eligible     = list({creator_oid} | set(approved_ids))   # deduplicated

        if caller_oid not in eligible:
            return Response(
                {'error': 'Only the creator or approved participants can complete a ride.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Atomic: add vote (idempotent — $addToSet ignores duplicates)
        rides.update_one(
            {'_id': ride_oid},
            {'$addToSet': {'completion_votes': caller_oid}},
        )

        # Re-fetch to get updated vote count
        ride         = rides.find_one({'_id': ride_oid})
        current_votes = ride.get('completion_votes', [])
        majority_needed = (len(eligible) // 2) + 1

        print(f'[COMPLETE] ride={ride_id_str} votes={len(current_votes)}/{majority_needed}')

        if len(current_votes) >= majority_needed:
            # Mark ride as COMPLETED
            rides.update_one(
                {'_id': ride_oid},
                {'$set': {'status': 'COMPLETED', 'completed_at': datetime.utcnow()}},
            )

            # Increment total_buddy_matches for all eligible users
            users = get_users_collection()
            users.update_many(
                {'_id': {'$in': eligible}},
                {'$inc': {'total_buddy_matches': 1}},
            )

            print(f'[COMPLETE] Ride {ride_id_str} COMPLETED — {len(eligible)} buddies matched')
            return Response({'message': 'Ride completed', 'status': 'COMPLETED'}, status=status.HTTP_200_OK)

        # Vote recorded but not yet majority
        return Response(
            {
                'message': 'Vote recorded',
                'votes': len(current_votes),
                'needed': majority_needed,
            },
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        print(f'[RIDE_COMPLETE ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to complete ride.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 8 — My Active Ride (used by home screen)
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def my_active_ride(request):
    """
    GET /rides/my-active

    Returns the caller's own ACTIVE ride (if any) with:
    - ride_id, ride_time, destination_name, max_seats
    - participants list: [{user_id, name, status}]
    Used by the home screen to show the "Complete Ride" button.
    """
    try:
        caller_id  = request.user_id
        caller_oid = ObjectId(caller_id)

        rides = get_rides_collection()
        ride  = rides.find_one({'creator_id': caller_oid, 'status': 'ACTIVE'})

        if not ride:
            return Response({'ride': None}, status=status.HTTP_200_OK)

        # Enrich participants with names
        users      = get_users_collection()
        enriched   = []
        for p in ride.get('participants', []):
            uid   = p.get('user_id')
            pstat = p.get('status', '')
            user  = users.find_one({'_id': uid}, {'full_name': 1, 'phone': 1})
            name  = (user or {}).get('full_name') or (user or {}).get('phone', 'Unknown')
            enriched.append({'user_id': str(uid), 'name': name, 'status': pstat})

        votes_count = len(ride.get('completion_votes', []))
        approved_count = sum(1 for p in enriched if p['status'] == 'APPROVED')
        total_eligible = approved_count + 1  # +1 for creator
        majority_needed = (total_eligible // 2) + 1

        return Response({
            'ride': {
                'ride_id':          str(ride['_id']),
                'ride_time':        ride.get('ride_time', ''),
                'destination_name': ride.get('destination', {}).get('name', ''),
                'max_seats':        ride.get('max_seats', 1),
                'participants':     enriched,
                'completion_votes': votes_count,
                'majority_needed':  majority_needed,
            }
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[MY_ACTIVE ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to fetch active ride.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
