"""
Users API Views — Block 4 + Block 9: Home Screen + Profile & Reputation
All endpoints require VERIFIED status (via verified_required decorator).
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from apps.verification.auth_middleware import verified_required
from database.mongo import get_users_collection, get_rides_collection, get_reviews_collection
from bson import ObjectId
from datetime import datetime


# ─────────────────────────────────────────────────────────
# GET /users/me  (extended Block 9)
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def get_me(request):
    """
    GET /users/me — full profile for authenticated user.
    """
    try:
        uid   = ObjectId(request.user_id)
        users = get_users_collection()
        user  = users.find_one({'_id': uid})

        if not user:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        rides   = get_rides_collection()
        reviews = get_reviews_collection()

        rides_completed = rides.count_documents({'creator_id': uid, 'status': 'COMPLETED'})
        reviews_count   = reviews.count_documents({'reviewee_id': uid})

        return Response({
            'user_id':             str(user['_id']),
            'phone':               user.get('phone', ''),
            'full_name':           user.get('full_name', ''),
            'bio':                 user.get('bio', ''),
            'rating':              user.get('rating', 0.0),
            'total_buddy_matches': user.get('total_buddy_matches', 0),
            'available_for_ride':  user.get('available_for_ride', False),
            'verification_status': user.get('verification_status', 'PENDING'),
            'rides_completed':     rides_completed,
            'reviews_count':       reviews_count,
            'gender':              user.get('gender', ''),
            'age':                 user.get('age', ''),
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[GET_ME ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to fetch user'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# PATCH /users/profile  (Block 9)
# ─────────────────────────────────────────────────────────
@api_view(['PATCH'])
@verified_required
def update_profile(request):
    """
    PATCH /users/profile
    Allowed: bio (max 150 chars), available_for_ride (bool)
    Forbidden: name, phone, verification_status
    """
    try:
        updates = {}

        bio = request.data.get('bio')
        if bio is not None:
            bio = str(bio).strip()
            if len(bio) > 150:
                return Response(
                    {'error': 'Bio must be 150 characters or fewer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
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

        updates['updated_at'] = datetime.utcnow()
        get_users_collection().update_one({'_id': ObjectId(request.user_id)}, {'$set': updates})

        print(f'[PROFILE_UPDATE] User {request.user_id} → {list(updates.keys())}')
        return Response({'message': 'Profile updated'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[UPDATE_PROFILE ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to update profile.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# PATCH /users/availability  (Block 4 — preserved)
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
            {'$set': {'available_for_ride': available, 'updated_at': datetime.utcnow()}},
        )
        return Response({'available_for_ride': available}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[AVAILABILITY ERROR] {e}')
        return Response({'error': 'Failed to update availability'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# PATCH /users/location  (Block 4 — preserved)
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
                'location':   {'type': 'Point', 'coordinates': [float(lng), float(lat)]},
                'updated_at': datetime.utcnow(),
            }},
        )
        return Response({'message': 'Location updated'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[LOCATION ERROR] {e}')
        return Response({'error': 'Failed to update location'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# GET /users/me/rides  (Block 9)
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def my_ride_history(request):
    """
    GET /users/me/rides
    Returns created[] and joined[] ride history, sorted newest first.
    """
    try:
        uid   = ObjectId(request.user_id)
        rides = get_rides_collection()

        def fmt(ride, role='creator'):
            participants  = ride.get('participants', [])
            approved      = sum(1 for p in participants if p.get('status') == 'APPROVED')
            return {
                'ride_id':          str(ride['_id']),
                'destination_name': ride.get('destination', {}).get('name', ''),
                'ride_date':        ride.get('ride_date', ''),
                'ride_time':        ride.get('ride_time', ''),
                'status':           ride.get('status', ''),
                'participant_count': approved + 1,   # +1 for creator
                'role':             role,
            }

        created_cursor = rides.find({'creator_id': uid}).sort('created_at', -1).limit(20)
        joined_cursor  = rides.find({
            'participants': {'$elemMatch': {'user_id': uid, 'status': 'APPROVED'}}
        }).sort('created_at', -1).limit(20)

        return Response({
            'created': [fmt(r, 'creator')   for r in created_cursor],
            'joined':  [fmt(r, 'passenger') for r in joined_cursor],
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[MY_RIDES ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to fetch ride history.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# GET /users/<user_id>  — Public Profile (Block 9)
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def public_profile(request, user_id):
    """
    GET /users/<user_id> — public view, hides phone/bio/location.
    """
    try:
        target_oid = ObjectId(user_id)
    except Exception:
        return Response({'error': 'Invalid user_id.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        users = get_users_collection()
        user  = users.find_one({'_id': target_oid})

        if not user:
            return Response({'error': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        rides   = get_rides_collection()
        reviews = get_reviews_collection()

        rides_completed = rides.count_documents({'creator_id': target_oid, 'status': 'COMPLETED'})
        reviews_count   = reviews.count_documents({'reviewee_id': target_oid})

        return Response({
            'user_id':             str(user['_id']),
            'full_name':           user.get('full_name', ''),
            'rating':              user.get('rating', 0.0),
            'total_buddy_matches': user.get('total_buddy_matches', 0),
            'verification_status': user.get('verification_status', 'PENDING'),
            'rides_completed':     rides_completed,
            'reviews_count':       reviews_count,
        }, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[PUBLIC_PROFILE ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to fetch profile.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


# ─────────────────────────────────────────────────────────
# GET /users/<user_id>/reviews  — Paginated (Block 9)
# ─────────────────────────────────────────────────────────
@api_view(['GET'])
@verified_required
def user_reviews(request, user_id):
    """
    GET /users/<user_id>/reviews?limit=5&offset=0
    Paginated reviews with reviewer_name.
    """
    try:
        target_oid = ObjectId(user_id)
    except Exception:
        return Response({'error': 'Invalid user_id.'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        limit  = int(request.query_params.get('limit',  5))
        offset = int(request.query_params.get('offset', 0))
        limit  = min(limit, 20)   # hard cap

        reviews = get_reviews_collection()
        users   = get_users_collection()

        cursor = (
            reviews.find({'reviewee_id': target_oid})
            .sort('created_at', -1)
            .skip(offset)
            .limit(limit)
        )

        result = []
        for rev in cursor:
            reviewer      = users.find_one({'_id': rev.get('reviewer_id')}, {'full_name': 1})
            reviewer_name = (reviewer or {}).get('full_name', 'Anonymous')
            result.append({
                'rating':        rev.get('rating', 0),
                'tags':          rev.get('tags', []),
                'created_at':    rev['created_at'].isoformat() if rev.get('created_at') else '',
                'reviewer_name': reviewer_name,
            })

        total = reviews.count_documents({'reviewee_id': target_oid})
        return Response({'reviews': result, 'total': total}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[USER_REVIEWS ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to fetch reviews.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
