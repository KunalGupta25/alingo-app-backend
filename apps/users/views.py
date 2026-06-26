"""
Users API Views — Profile & Reputation
All endpoints require VERIFIED status.
"""
import re
import logging
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from apps.verification.auth_middleware import verified_required
from database.mongo import get_users_collection, get_rides_collection, get_reviews_collection
from bson import ObjectId
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _sanitize(value: str, max_len: int = 200) -> str:
    """Strip whitespace and HTML tags from user input."""
    if not isinstance(value, str):
        return ''
    value = value.strip()
    value = re.sub(r'<[^>]+>', '', value)
    return value[:max_len]


def _rides_completed_count(uid: ObjectId, rides) -> int:
    """Count completed rides as creator OR approved participant."""
    created = rides.count_documents({'creator_id': uid, 'status': 'COMPLETED'})
    joined = rides.count_documents({
        'status': 'COMPLETED',
        'participants': {'$elemMatch': {'user_id': uid, 'status': 'APPROVED'}},
    })
    return created + joined


# ─────────────────────────────────────────────────────────
# GET /users/me
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def get_me(request):
    """GET /users/me — full profile for authenticated user."""
    try:
        uid = ObjectId(request.user_id)
        users = get_users_collection()
        user = users.find_one({'_id': uid})

        if not user:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        rides = get_rides_collection()
        reviews = get_reviews_collection()

        rides_completed = _rides_completed_count(uid, rides)
        reviews_count = reviews.count_documents({'reviewee_id': uid})

        return Response({
            'user_id': str(user['_id']),
            'phone': user.get('phone', ''),
            'full_name': user.get('full_name', ''),
            'bio': user.get('bio', ''),
            'rating': user.get('rating', 0.0),
            'total_buddy_matches': user.get('total_buddy_matches', 0),
            'available_for_ride': user.get('available_for_ride', False),
            'verification_status': user.get('verification_status', 'PENDING'),
            'rides_completed': rides_completed,
            'reviews_count': reviews_count,
            'gender': user.get('gender', ''),
            'dob': user.get('dob', ''),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[GET_ME ERROR] %s', e)
        return Response({'error': 'Failed to fetch user'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# PATCH /users/profile
# ─────────────────────────────────────────────────────────
@api_view(['PATCH'])
@verified_required
def update_profile(request):
    """PATCH /users/profile — update bio and availability."""
    try:
        updates = {}

        bio = request.data.get('bio')
        if bio is not None:
            bio = _sanitize(str(bio), 150)
            updates['bio'] = bio

        available = request.data.get('available_for_ride')
        if available is not None:
            if not isinstance(available, bool):
                return Response(
                    {'error': 'available_for_ride must be a boolean.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            updates['available_for_ride'] = available

        if not updates:
            return Response({'error': 'No valid fields provided.'}, status=status.HTTP_400_BAD_REQUEST)

        updates['updated_at'] = datetime.now(timezone.utc)
        get_users_collection().update_one({'_id': ObjectId(request.user_id)}, {'$set': updates})

        logger.info('[PROFILE_UPDATE] User %s → %s', request.user_id, list(updates.keys()))
        return Response({'message': 'Profile updated'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[UPDATE_PROFILE ERROR] %s', e)
        return Response({'error': 'Failed to update profile.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# PATCH /users/availability
# ─────────────────────────────────────────────────────────
@api_view(['PATCH'])
@verified_required
def update_availability(request):
    """PATCH /users/availability — toggle available_for_ride."""
    try:
        available = request.data.get('available_for_ride')
        if available is None:
            return Response({'error': 'available_for_ride is required'}, status=status.HTTP_400_BAD_REQUEST)
        if not isinstance(available, bool):
            return Response({'error': 'available_for_ride must be a boolean'}, status=status.HTTP_400_BAD_REQUEST)

        get_users_collection().update_one(
            {'_id': ObjectId(request.user_id)},
            {'$set': {'available_for_ride': available, 'updated_at': datetime.now(timezone.utc)}},
        )
        return Response({'available_for_ride': available}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[AVAILABILITY ERROR] %s', e)
        return Response({'error': 'Failed to update availability'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# PATCH /users/location
# ─────────────────────────────────────────────────────────
@api_view(['PATCH'])
@verified_required
def update_location(request):
    """PATCH /users/location — store GeoJSON point."""
    try:
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')
        if lat is None or lng is None:
            return Response({'error': 'latitude and longitude are required'}, status=status.HTTP_400_BAD_REQUEST)

        get_users_collection().update_one(
            {'_id': ObjectId(request.user_id)},
            {'$set': {
                'location': {'type': 'Point', 'coordinates': [float(lng), float(lat)]},
                'updated_at': datetime.now(timezone.utc),
            }},
        )
        return Response({'message': 'Location updated'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[LOCATION ERROR] %s', e)
        return Response({'error': 'Failed to update location'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# GET /users/me/rides
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def my_ride_history(request):
    """GET /users/me/rides — created and joined ride history."""
    try:
        uid = ObjectId(request.user_id)
        rides = get_rides_collection()

        def fmt(ride, role='creator'):
            participants = ride.get('participants', [])
            approved = sum(1 for p in participants if p.get('status') == 'APPROVED')
            return {
                'ride_id': str(ride['_id']),
                'destination_name': ride.get('destination', {}).get('name', ''),
                'ride_date': ride.get('ride_date', ''),
                'ride_time': ride.get('ride_time', ''),
                'status': ride.get('status', ''),
                'participant_count': approved + 1,
                'role': role,
            }

        created_cursor = rides.find({'creator_id': uid}).sort('created_at', -1).limit(20)
        joined_cursor = rides.find({
            'creator_id': {'$ne': uid},
            'participants': {'$elemMatch': {'user_id': uid, 'status': 'APPROVED'}}
        }).sort('created_at', -1).limit(20)

        return Response({
            'created': [fmt(r, 'creator') for r in created_cursor],
            'joined': [fmt(r, 'passenger') for r in joined_cursor],
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[MY_RIDES ERROR] %s', e)
        return Response({'error': 'Failed to fetch ride history.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# GET /users/<user_id> — Public Profile
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def public_profile(request, user_id):
    """GET /users/<user_id> — public view, hides phone/bio/location."""
    try:
        target_oid = ObjectId(user_id)
    except Exception:
        return Response({'error': 'Invalid user_id.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        users = get_users_collection()
        user = users.find_one({'_id': target_oid})

        if not user:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        rides = get_rides_collection()
        reviews = get_reviews_collection()

        rides_completed = _rides_completed_count(target_oid, rides)
        reviews_count = reviews.count_documents({'reviewee_id': target_oid})

        return Response({
            'user_id': str(user['_id']),
            'full_name': user.get('full_name', ''),
            'rating': user.get('rating', 0.0),
            'total_buddy_matches': user.get('total_buddy_matches', 0),
            'verification_status': user.get('verification_status', 'PENDING'),
            'rides_completed': rides_completed,
            'reviews_count': reviews_count,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[PUBLIC_PROFILE ERROR] %s', e)
        return Response({'error': 'Failed to fetch profile.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# GET /users/<user_id>/reviews — Paginated
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def user_reviews(request, user_id):
    """GET /users/<user_id>/reviews?limit=5&offset=0"""
    try:
        target_oid = ObjectId(user_id)
    except Exception:
        return Response({'error': 'Invalid user_id.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        limit = min(int(request.query_params.get('limit', 5)), 20)
        offset = int(request.query_params.get('offset', 0))

        reviews = get_reviews_collection()
        cursor = (
            reviews.find({'reviewee_id': target_oid})
            .sort('created_at', -1)
            .skip(offset)
            .limit(limit)
        )
        review_list = list(cursor)

        # ── Batch fetch reviewer names in ONE query ──
        reviewer_oids = [r['reviewer_id'] for r in review_list if r.get('reviewer_id')]
        users = get_users_collection()
        reviewer_docs = users.find({'_id': {'$in': reviewer_oids}}, {'full_name': 1})
        reviewer_map = {doc['_id']: doc for doc in reviewer_docs}

        result = []
        for rev in review_list:
            reviewer_doc = reviewer_map.get(rev.get('reviewer_id'), {})
            result.append({
                'rating': rev.get('rating', 0),
                'tags': rev.get('tags', []),
                'created_at': rev['created_at'].isoformat() if rev.get('created_at') else '',
                'reviewer_name': reviewer_doc.get('full_name', 'Anonymous'),
            })

        total = reviews.count_documents({'reviewee_id': target_oid})
        return Response({'reviews': result, 'total': total}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[USER_REVIEWS ERROR] %s', e)
        return Response({'error': 'Failed to fetch reviews.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# POST /users/push-token
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def register_push_token(request):
    """POST /users/push-token — Store Expo push token."""
    try:
        token = request.data.get('token')
        if not token:
            return Response({'error': 'token is required.'}, status=status.HTTP_400_BAD_REQUEST)

        get_users_collection().update_one(
            {'_id': ObjectId(request.user_id)},
            {'$set': {'expo_push_token': token}},
        )

        logger.info('[PUSH TOKEN] Stored for user %s', request.user_id)
        return Response({'message': 'Push token registered.'}, status=status.HTTP_200_OK)

    except Exception as e:
        logger.exception('[PUSH TOKEN ERROR] %s', e)
        return Response({'error': 'Failed to register push token.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
