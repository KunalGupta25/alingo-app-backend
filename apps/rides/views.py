"""
Rides API Views — Block 5-10
All endpoints require VERIFIED status.
"""
import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import date, datetime, timezone
from bson import ObjectId
from django.utils import timezone as dj_timezone

from apps.verification.auth_middleware import verified_required
from database.mongo import get_users_collection, get_rides_collection
from .services import RideService
from apps.users.notifications import send_push_notification, send_bulk_notifications

logger = logging.getLogger(__name__)


def _batch_fetch_users(user_ids: list) -> dict:
    """Batch fetch users by ObjectId list. Returns {oid: doc} dict."""
    if not user_ids:
        return {}
    users = get_users_collection()
    docs = users.find(
        {'_id': {'$in': user_ids}},
        {'full_name': 1, 'phone': 1},
    )
    return {doc['_id']: doc for doc in docs}


def _ist_today() -> date:
    """
    'Today' in IST, not the server's local/UTC clock. Render runs UTC, but all
    users are in India — without this, "ride date cannot be in the past"
    checks would drift against what users actually experience as today.
    Requires settings.TIME_ZONE = 'Asia/Kolkata'.
    """
    return dj_timezone.localtime(dj_timezone.now()).date()


def _sanitize_str(value: str, max_len: int = 200) -> str:
    """Strip whitespace and basic HTML-like tags from user input."""
    import re
    if not isinstance(value, str):
        return ''
    value = value.strip()
    value = re.sub(r'<[^>]+>', '', value)
    return value[:max_len]


# ─────────────────────────────────────────────────────────
# BLOCK 5 — Create Ride
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def create_ride(request):
    """POST /rides/create"""
    try:
        user_id = request.user_id
        users = get_users_collection()
        user = users.find_one({'_id': ObjectId(user_id)})

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

        destination = request.data.get('destination')
        ride_date_str = request.data.get('ride_date')
        ride_time = request.data.get('ride_time')
        max_seats = request.data.get('max_seats')
        route_polyline = request.data.get('route_polyline', '')
        gender_preference = request.data.get('gender_preference', 'Any')

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

        # Sanitize destination name
        destination['name'] = _sanitize_str(destination['name'], 150)

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

        if ride_date < _ist_today():
            return Response({'error': 'Ride date cannot be in the past.'}, status=status.HTTP_400_BAD_REQUEST)

        ride = RideService.create_ride(
            creator_id=user_id,
            start_location=start_location,
            destination=destination,
            ride_date=ride_date_str,
            ride_time=ride_time,
            max_seats=max_seats,
            route_polyline=route_polyline,
            gender_preference=gender_preference,
        )

        logger.info('[RIDE_CREATE] User %s → %s on %s', user_id, destination['name'], ride_date_str)
        return Response({
            'ride_id': str(ride['_id']),
            'status': ride['status'],
            'destination': ride['destination']['name'],
            'ride_date': ride['ride_date'],
            'ride_time': ride['ride_time'],
            'max_seats': ride['max_seats'],
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        logger.exception('[RIDE_CREATE ERROR] %s', e)
        return Response({'error': 'Failed to create ride.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 6 — Search Rides
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def search_rides(request):
    """POST /rides/search"""
    try:
        user_id = request.user_id
        user_location = request.data.get('user_location')
        ride_date_str = request.data.get('ride_date')
        route_polyline = request.data.get('route_polyline', '')
        gender_filter = request.data.get('gender_filter', 'All')

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

        if ride_date < _ist_today():
            return Response({'error': 'ride_date cannot be in the past.'}, status=status.HTTP_400_BAD_REQUEST)

        search_time = request.data.get('ride_time')  # optional 'HH:MM' — when the searcher wants to travel
        time_window_minutes = request.data.get('time_window_minutes', 90)
        try:
            time_window_minutes = int(time_window_minutes)
        except (ValueError, TypeError):
            time_window_minutes = 90

        matches = RideService.search_rides(
            user_id=user_id,
            user_location=[float(user_location[0]), float(user_location[1])],
            ride_date=ride_date_str,
            user_polyline=route_polyline,
            gender_filter=gender_filter,
            search_time=search_time,
            time_window_minutes=time_window_minutes,
        )

        return Response(matches, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[RIDE_SEARCH ERROR] %s', e)
        return Response({'error': 'Search failed.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 7 — Request to Join
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def request_ride(request):
    """POST /rides/request"""
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
        ride = rides.find_one({'_id': ride_oid})

        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        if ride.get('status') != 'ACTIVE':
            return Response({'error': 'This ride is no longer active.'}, status=status.HTTP_400_BAD_REQUEST)

        if ride['creator_id'] == user_oid:
            return Response({'error': 'You cannot request to join your own ride.'}, status=status.HTTP_400_BAD_REQUEST)

        participants = ride.get('participants', [])
        already = next((p for p in participants if p.get('user_id') == user_oid), None)
        if already:
            existing_status = already.get('status', '')
            if existing_status == 'PENDING':
                return Response({'error': 'Your request is already pending.'}, status=status.HTTP_409_CONFLICT)
            if existing_status == 'APPROVED':
                return Response({'error': 'You are already in this ride.'}, status=status.HTTP_409_CONFLICT)
            if existing_status == 'REJECTED':
                return Response({'error': 'Your request was rejected by the creator.'}, status=status.HTTP_409_CONFLICT)

        approved_count = sum(1 for p in participants if p.get('status') == 'APPROVED')
        if approved_count >= ride.get('max_seats', 1):
            return Response({'error': 'This ride is full.'}, status=status.HTTP_400_BAD_REQUEST)

        rides.update_one(
            {'_id': ride_oid},
            {'$push': {'participants': {'user_id': user_oid, 'status': 'PENDING'}}},
        )

        logger.info('[RIDE_REQUEST] User %s → ride %s', user_id, ride_id_str)

        # Notify creator — batch fetch (single user but consistent pattern)
        user_map = _batch_fetch_users([user_oid])
        requester = user_map.get(user_oid, {})
        requester_name = requester.get('full_name') or requester.get('phone', 'Someone')
        dest_name = ride.get('destination', {}).get('name', 'a ride')
        send_push_notification(
            ride['creator_id'],
            'New Ride Request 🙋',
            f'{requester_name} wants to join your ride to {dest_name}',
            {'type': 'ride_request', 'ride_id': ride_id_str},
        )

        return Response({'message': 'Request sent'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[RIDE_REQUEST ERROR] %s', e)
        return Response({'error': 'Failed to send request.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 7 — Creator Responds
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def respond_ride(request):
    """POST /rides/respond"""
    try:
        caller_id = request.user_id
        ride_id_str = request.data.get('ride_id')
        target_id_str = request.data.get('user_id')
        action = request.data.get('action', '').upper()

        if not ride_id_str or not target_id_str or not action:
            return Response(
                {'error': 'ride_id, user_id, and action are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if action not in ('APPROVE', 'REJECT'):
            return Response({'error': 'action must be APPROVE or REJECT.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride_oid = ObjectId(ride_id_str)
            target_oid = ObjectId(target_id_str)
            caller_oid = ObjectId(caller_id)
        except Exception:
            return Response({'error': 'Invalid ObjectId.'}, status=status.HTTP_400_BAD_REQUEST)

        rides = get_rides_collection()
        ride = rides.find_one({'_id': ride_oid})

        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        if ride['creator_id'] != caller_oid:
            return Response({'error': 'Only the ride creator can respond to requests.'}, status=status.HTTP_403_FORBIDDEN)

        if ride.get('status') != 'ACTIVE':
            return Response({'error': 'Cannot respond after the ride is completed or cancelled.'}, status=status.HTTP_400_BAD_REQUEST)

        participants = ride.get('participants', [])
        target = next((p for p in participants if p.get('user_id') == target_oid), None)
        if not target:
            return Response({'error': 'User has not requested to join this ride.'}, status=status.HTTP_404_NOT_FOUND)

        if target.get('status') != 'PENDING':
            return Response(
                {'error': f'Request is already {target["status"].lower()}.'},
                status=status.HTTP_409_CONFLICT,
            )

        if action == 'APPROVE':
            approved_count = sum(1 for p in participants if p.get('status') == 'APPROVED')
            if approved_count >= ride.get('max_seats', 1):
                return Response({'error': 'Ride is full. Cannot approve more riders.'}, status=status.HTTP_400_BAD_REQUEST)

        new_status = 'APPROVED' if action == 'APPROVE' else 'REJECTED'
        result = rides.update_one(
            {'_id': ride_oid, 'participants.user_id': target_oid},
            {'$set': {'participants.$.status': new_status}},
        )

        if result.modified_count == 0:
            return Response({'error': 'Update failed. Please try again.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        logger.info('[RIDE_RESPOND] Creator %s → %s user %s on ride %s', caller_id, action, target_id_str, ride_id_str)

        dest_name = ride.get('destination', {}).get('name', 'the ride')
        if action == 'APPROVE':
            send_push_notification(
                target_oid, 'Request Approved ✅',
                f'Your request to join the ride to {dest_name} was approved!',
                {'type': 'ride_approved', 'ride_id': ride_id_str},
            )
        else:
            send_push_notification(
                target_oid, 'Request Declined',
                f'Your request to join the ride to {dest_name} was declined.',
                {'type': 'ride_rejected', 'ride_id': ride_id_str},
            )

        return Response({'message': 'User approved' if action == 'APPROVE' else 'User rejected'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[RIDE_RESPOND ERROR] %s', e)
        return Response({'error': 'Failed to respond.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 8 — Complete Ride (Majority Vote)
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def complete_ride(request):
    """POST /rides/complete"""
    try:
        caller_id = request.user_id
        ride_id_str = request.data.get('ride_id')

        if not ride_id_str:
            return Response({'error': 'ride_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride_oid = ObjectId(ride_id_str)
            caller_oid = ObjectId(caller_id)
        except Exception:
            return Response({'error': 'Invalid ride_id.'}, status=status.HTTP_400_BAD_REQUEST)

        rides = get_rides_collection()
        ride = rides.find_one({'_id': ride_oid})

        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        if ride.get('status') != 'ACTIVE':
            return Response({'error': 'Ride is not active.'}, status=status.HTTP_400_BAD_REQUEST)

        participants = ride.get('participants', [])
        approved_ids = [p['user_id'] for p in participants if p.get('status') == 'APPROVED']
        creator_oid = ride['creator_id']
        eligible = list({creator_oid} | set(approved_ids))

        if caller_oid not in eligible:
            return Response(
                {'error': 'Only the creator or approved participants can complete a ride.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        rides.update_one({'_id': ride_oid}, {'$addToSet': {'completion_votes': caller_oid}})

        ride = rides.find_one({'_id': ride_oid})
        current_votes = ride.get('completion_votes', [])
        majority_needed = (len(eligible) // 2) + 1

        logger.info('[COMPLETE] ride=%s votes=%d/%d', ride_id_str, len(current_votes), majority_needed)

        if len(current_votes) >= majority_needed:
            rides.update_one(
                {'_id': ride_oid},
                {'$set': {'status': 'COMPLETED', 'completed_at': datetime.now(timezone.utc)}},
            )

            users = get_users_collection()
            users.update_many({'_id': {'$in': eligible}}, {'$inc': {'total_buddy_matches': 1}})

            logger.info('[COMPLETE] Ride %s COMPLETED — %d buddies matched', ride_id_str, len(eligible))

            dest_name = ride.get('destination', {}).get('name', 'your destination')
            other_ids = [uid for uid in eligible if uid != caller_oid]
            if other_ids:
                send_bulk_notifications(
                    other_ids, 'Ride Completed 🎉',
                    f'Your ride to {dest_name} has been completed! Don\'t forget to leave a review.',
                    {'type': 'ride_completed', 'ride_id': ride_id_str},
                )

            return Response({'message': 'Ride completed', 'status': 'COMPLETED'}, status=status.HTTP_200_OK)

        return Response(
            {'message': 'Vote recorded', 'votes': len(current_votes), 'needed': majority_needed},
            status=status.HTTP_200_OK,
        )

    except Exception as e:
        logger.exception('[RIDE_COMPLETE ERROR] %s', e)
        return Response({'error': 'Failed to complete ride.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK X — Cancel Ride
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def cancel_ride(request):
    """POST /rides/cancel"""
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
        ride = rides.find_one({'_id': ride_oid})

        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        if ride.get('creator_id') != user_oid:
            return Response({'error': 'Only the creator can cancel this ride.'}, status=status.HTTP_403_FORBIDDEN)

        if ride.get('status') != 'ACTIVE':
            return Response({'error': 'Only active rides can be canceled.'}, status=status.HTTP_400_BAD_REQUEST)

        rides.update_one({'_id': ride_oid}, {'$set': {'status': 'CANCELED'}})

        participants = ride.get('participants', [])
        approved_ids = [p['user_id'] for p in participants if p.get('status') == 'APPROVED']
        if approved_ids:
            dest_name = ride.get('destination', {}).get('name', 'a ride')
            send_bulk_notifications(
                approved_ids, 'Ride Cancelled ❌',
                f'The ride to {dest_name} has been cancelled by the creator.',
                {'type': 'ride_cancelled', 'ride_id': str(ride_oid)},
            )

        return Response({'message': 'Ride canceled successfully.'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[RIDE_CANCEL ERROR] %s', e)
        return Response({'error': 'Failed to cancel the ride.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 8 — My Active Ride
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def my_active_ride(request):
    """GET /rides/my-active"""
    try:
        caller_id = request.user_id
        caller_oid = ObjectId(caller_id)
        rides = get_rides_collection()

        ride = rides.find_one({'creator_id': caller_oid, 'status': 'ACTIVE'})
        is_creator = True

        if not ride:
            ride = rides.find_one({
                'status': 'ACTIVE',
                'participants': {'$elemMatch': {'user_id': caller_oid, 'status': 'APPROVED'}}
            })
            is_creator = False

        if not ride:
            return Response({'ride': None}, status=status.HTTP_200_OK)

        # ── Batch fetch all participant users in ONE query ──
        participant_oids = [p['user_id'] for p in ride.get('participants', []) if p.get('user_id')]
        user_map = _batch_fetch_users(participant_oids)

        enriched = []
        for p in ride.get('participants', []):
            uid = p.get('user_id')
            doc = user_map.get(uid, {})
            enriched.append({
                'user_id': str(uid),
                'name': doc.get('full_name') or doc.get('phone', 'Unknown'),
                'phone': doc.get('phone', ''),
                'status': p.get('status', ''),
            })

        votes_count = len(ride.get('completion_votes', []))
        has_voted = caller_oid in ride.get('completion_votes', [])
        approved_count = sum(1 for p in enriched if p['status'] == 'APPROVED')
        total_eligible = approved_count + 1
        majority_needed = (total_eligible // 2) + 1

        return Response({'ride': {
            'ride_id': str(ride['_id']),
            'ride_time': ride.get('ride_time', ''),
            'destination_name': ride.get('destination', {}).get('name', ''),
            'max_seats': ride.get('max_seats', 1),
            'participants': enriched,
            'completion_votes': votes_count,
            'majority_needed': majority_needed,
            'has_voted': has_voted,
            'is_creator': is_creator,
            'creator_id': str(ride['creator_id']),
            'route_polyline': ride.get('route_polyline', ''),
        }}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[MY_ACTIVE ERROR] %s', e)
        return Response({'error': 'Failed to fetch active ride.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 9 — My Ride Requests
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def my_requests(request):
    """GET /rides/my-requests"""
    try:
        caller_id = request.user_id
        caller_oid = ObjectId(caller_id)
        rides = get_rides_collection()

        cursor = rides.find({
            'status': 'ACTIVE',
            'creator_id': {'$ne': caller_oid},
            'participants': {'$elemMatch': {
                'user_id': caller_oid,
                'status': {'$in': ['PENDING', 'APPROVED', 'REJECTED']},
            }}
        })

        ride_list = list(cursor)

        # ── Batch fetch all creators in ONE query ──
        creator_oids = list({r['creator_id'] for r in ride_list})
        creator_map = _batch_fetch_users(creator_oids)

        result = []
        for ride in ride_list:
            my_entry = next(
                (p for p in ride.get('participants', []) if p.get('user_id') == caller_oid),
                None,
            )
            if not my_entry:
                continue

            creator_doc = creator_map.get(ride['creator_id'], {})
            creator_name = creator_doc.get('full_name') or creator_doc.get('phone', 'Unknown')

            result.append({
                'ride_id': str(ride['_id']),
                'ride_time': ride.get('ride_time', ''),
                'destination_name': ride.get('destination', {}).get('name', ''),
                'creator_name': creator_name,
                'creator_id': str(ride['creator_id']),
                'my_status': my_entry.get('status', ''),
            })

        return Response({'requests': result}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[MY_REQUESTS ERROR] %s', e)
        return Response({'error': 'Failed to fetch ride requests.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# BLOCK 10 — Ride Detail
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def ride_detail(request):
    """GET /rides/detail?ride_id=<ride_id>"""
    try:
        ride_id = request.query_params.get('ride_id')
        if not ride_id:
            return Response({'error': 'ride_id is required.'}, status=status.HTTP_400_BAD_REQUEST)

        rides = get_rides_collection()
        ride = rides.find_one({'_id': ObjectId(ride_id)})
        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        # ── Batch fetch participants + creator in ONE query ──
        participant_oids = [p['user_id'] for p in ride.get('participants', []) if p.get('user_id')]
        all_oids = list(set(participant_oids + [ride['creator_id']]))
        user_map = _batch_fetch_users(all_oids)

        enriched = []
        for p in ride.get('participants', []):
            uid = p.get('user_id')
            doc = user_map.get(uid, {})
            enriched.append({
                'user_id': str(uid),
                'name': doc.get('full_name') or doc.get('phone', 'Unknown'),
                'phone': doc.get('phone', ''),
                'status': p.get('status', ''),
            })

        creator_doc = user_map.get(ride['creator_id'], {})
        creator_name = creator_doc.get('full_name') or creator_doc.get('phone', 'Unknown')
        dest = ride.get('destination', {})

        return Response({
            'ride_id': str(ride['_id']),
            'status': ride.get('status', ''),
            'destination_name': dest.get('name', ''),
            'destination_coords': dest.get('coordinates', []),
            'ride_date': ride.get('ride_date', ''),
            'ride_time': ride.get('ride_time', ''),
            'max_seats': ride.get('max_seats', 1),
            'route_polyline': ride.get('route_polyline', ''),
            'creator_id': str(ride['creator_id']),
            'creator_name': creator_name,
            'participants': enriched,
            'gender_preference': ride.get('gender_preference', 'Any'),
            'created_at': str(ride.get('created_at', '')),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[RIDE_DETAIL ERROR] %s', e)
        return Response({'error': 'Failed to fetch ride details.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
