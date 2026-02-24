"""
Reviews API Views — Block 8
POST /reviews/create  →  verified_required
"""
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from datetime import datetime, timezone
from bson import ObjectId
from pymongo.errors import DuplicateKeyError

from database.mongo import get_reviews_collection, get_rides_collection, get_users_collection
from apps.verification.auth_middleware import verified_required


# ─────────────────────────────────────────────────────────
# Helper — Recalculate and persist a user's avg rating
# ─────────────────────────────────────────────────────────
def _recalculate_rating(reviewee_oid: ObjectId):
    """
    Aggregates all reviews for reviewee_oid, computes the average rating,
    and writes it back to the users collection.
    """
    reviews  = get_reviews_collection()
    users    = get_users_collection()

    pipeline = [
        {'$match': {'reviewee_id': reviewee_oid}},
        {'$group': {'_id': '$reviewee_id', 'avg_rating': {'$avg': '$rating'}}},
    ]
    result = list(reviews.aggregate(pipeline))
    if result:
        avg = round(result[0]['avg_rating'], 2)
        users.update_one({'_id': reviewee_oid}, {'$set': {'rating': avg}})


# ─────────────────────────────────────────────────────────
# POST /reviews/create
# ─────────────────────────────────────────────────────────
@api_view(['POST'])
@verified_required
def create_review(request):
    """
    POST /reviews/create
    Body:
    {
        "ride_id":     "<ObjectId>",
        "reviewee_id": "<ObjectId>",
        "rating":      4,            # 1-5 integer
        "tags":        ["On time"]   # optional list of strings
    }

    Rules:
    - Ride must be COMPLETED
    - Reviewer must be creator or APPROVED participant
    - Reviewee must be creator or APPROVED participant
    - Cannot review self
    - Cannot review same user twice (unique index enforces this)
    - Updates reviewee's average rating
    """
    try:
        caller_id     = request.user_id
        ride_id_str   = request.data.get('ride_id')
        reviewee_str  = request.data.get('reviewee_id')
        rating        = request.data.get('rating')
        tags          = request.data.get('tags', [])

        # ── Validate required fields ──
        if not ride_id_str or not reviewee_str or rating is None:
            return Response(
                {'error': 'ride_id, reviewee_id, and rating are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            rating = int(rating)
        except (TypeError, ValueError):
            return Response({'error': 'rating must be an integer.'}, status=status.HTTP_400_BAD_REQUEST)

        if not (1 <= rating <= 5):
            return Response({'error': 'rating must be between 1 and 5.'}, status=status.HTTP_400_BAD_REQUEST)

        if not isinstance(tags, list):
            return Response({'error': 'tags must be a list.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ride_oid     = ObjectId(ride_id_str)
            reviewee_oid = ObjectId(reviewee_str)
            reviewer_oid = ObjectId(caller_id)
        except Exception:
            return Response({'error': 'Invalid ObjectId.'}, status=status.HTTP_400_BAD_REQUEST)

        if reviewer_oid == reviewee_oid:
            return Response({'error': 'You cannot review yourself.'}, status=status.HTTP_400_BAD_REQUEST)

        # ── Fetch and validate ride ──
        rides = get_rides_collection()
        ride  = rides.find_one({'_id': ride_oid})

        if not ride:
            return Response({'error': 'Ride not found.'}, status=status.HTTP_404_NOT_FOUND)

        if ride.get('status') != 'COMPLETED':
            return Response(
                {'error': 'You can only review after the ride is completed.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Build eligible users set (creator + APPROVED participants) ──
        participants    = ride.get('participants', [])
        approved_ids    = {p['user_id'] for p in participants if p.get('status') == 'APPROVED'}
        creator_oid     = ride['creator_id']
        eligible_ids    = approved_ids | {creator_oid}

        if reviewer_oid not in eligible_ids:
            return Response(
                {'error': 'Only approved participants can leave reviews.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if reviewee_oid not in eligible_ids:
            return Response(
                {'error': 'The reviewee was not part of this ride.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Insert review (unique index prevents duplicates) ──
        reviews = get_reviews_collection()
        try:
            reviews.insert_one({
                'ride_id':     ride_oid,
                'reviewer_id': reviewer_oid,
                'reviewee_id': reviewee_oid,
                'rating':      rating,
                'tags':        [str(t) for t in tags],
                'created_at':  datetime.now(timezone.utc),
            })
        except DuplicateKeyError:
            return Response(
                {'error': 'You have already reviewed this person for this ride.'},
                status=status.HTTP_409_CONFLICT,
            )

        # ── Recalculate reviewee's average rating ──
        _recalculate_rating(reviewee_oid)

        print(f'[REVIEW] {caller_id} → {reviewee_str} | ride={ride_id_str} | rating={rating}')
        return Response({'message': 'Review submitted'}, status=status.HTTP_200_OK)

    except Exception as e:
        print(f'[REVIEW ERROR] {e}')
        import traceback; traceback.print_exc()
        return Response({'error': 'Failed to submit review.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
