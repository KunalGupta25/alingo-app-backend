"""
Rides Service — Block 5 + Block 6
Ride creation, searching, and route matching.
"""
import math
from datetime import datetime, timezone
from bson import ObjectId
from database.mongo import get_rides_collection


# ── Polyline Decoder (OSRM / Google encoded polyline) ─────
def decode_polyline(polyline_str: str) -> list[tuple[float, float]]:
    """
    Decode an encoded polyline string into a list of (lat, lng) tuples.
    Implements the standard Google/OSRM polyline algorithm.
    Returns [] if string is empty or invalid.
    """
    if not polyline_str:
        return []
    coords, index, lat, lng = [], 0, 0, 0
    try:
        while index < len(polyline_str):
            # Decode latitude
            result, shift, b = 0, 0, 0
            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            dlat = ~(result >> 1) if result & 1 else result >> 1
            lat += dlat

            # Decode longitude
            result, shift, b = 0, 0, 0
            while True:
                b = ord(polyline_str[index]) - 63
                index += 1
                result |= (b & 0x1F) << shift
                shift += 5
                if b < 0x20:
                    break
            dlng = ~(result >> 1) if result & 1 else result >> 1
            lng += dlng

            coords.append((lat / 1e5, lng / 1e5))
    except (IndexError, ValueError):
        pass
    return coords


# ── Haversine distance (metres) ───────────────────────────
def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi  = math.radians(lat2 - lat1)
    dlam  = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


# ── Route overlap (user_coords vs ride_coords) ────────────
def route_overlap_pct(
    user_coords: list[tuple[float, float]],
    ride_coords: list[tuple[float, float]],
    threshold_m: float = 100.0,
) -> float:
    """
    % of user route points that are within `threshold_m` of any ride point.
    Returns 0.0 if either list is empty (no polylines stored → skip filter).
    """
    if not user_coords or not ride_coords:
        return 100.0   # no polylines → don't reject on overlap

    matches = 0
    for ulat, ulng in user_coords:
        for rlat, rlng in ride_coords:
            if haversine_m(ulat, ulng, rlat, rlng) <= threshold_m:
                matches += 1
                break
    return (matches / len(user_coords)) * 100.0


class RideService:

    # ── Block 5 ───────────────────────────────────────────
    @staticmethod
    def get_active_ride_for_user(creator_id: str):
        rides = get_rides_collection()
        return rides.find_one({
            'creator_id': ObjectId(creator_id),
            'status':     'ACTIVE',
        })

    @staticmethod
    def create_ride(
        creator_id: str,
        start_location: dict,
        destination: dict,
        ride_date: str,
        ride_time: str,
        max_seats: int,
        route_polyline: str,
    ) -> dict:
        rides = get_rides_collection()
        ride_doc = {
            'creator_id':     ObjectId(creator_id),
            'start_location': start_location,
            'destination':    destination,
            'route_polyline': route_polyline,
            'ride_date':      ride_date,
            'ride_time':      ride_time,
            'max_seats':      max_seats,
            'participants': [{
                'user_id': ObjectId(creator_id),
                'status':  'APPROVED',
            }],
            'status':     'ACTIVE',
            'created_at': datetime.now(timezone.utc),
        }
        result = rides.insert_one(ride_doc)
        ride_doc['_id'] = result.inserted_id
        return ride_doc

    # ── Block 6 ───────────────────────────────────────────
    @staticmethod
    def search_rides(
        user_id:        str,
        user_location:  list,            # [lng, lat]
        ride_date:      str,             # 'YYYY-MM-DD'
        user_polyline:  str = '',
        min_overlap_pct: float = 50.0,
    ) -> list[dict]:
        """
        5-step matching pipeline.
        Returns a ranked list of ride dicts with enriched creator info.
        """
        from database.mongo import get_users_collection

        rides      = get_rides_collection()
        users_col  = get_users_collection()
        user_oid   = ObjectId(user_id)
        user_coords = decode_polyline(user_polyline)

        # ── STEP 1 + 2  Filter by date & 500m geo radius ──
        try:
            cursor = rides.find({
                'status':    'ACTIVE',
                'ride_date': ride_date,
                'start_location': {
                    '$nearSphere': {
                        '$geometry': {
                            'type':        'Point',
                            'coordinates': user_location,  # [lng, lat]
                        },
                        '$maxDistance': 500,  # metres
                    }
                },
            })
            candidates = list(cursor)
        except Exception as e:
            print(f'[SEARCH GEO ERROR] {e}')
            # Fallback: skip geo filter if 2dsphere index missing
            candidates = list(rides.find({
                'status':    'ACTIVE',
                'ride_date': ride_date,
            }))

        results = []
        for ride in candidates:

            # ── STEP 3 — Exclusions ──────────────────────
            # Skip own ride
            if ride['creator_id'] == user_oid:
                continue

            participants    = ride.get('participants', [])
            approved_count  = sum(1 for p in participants if p.get('status') == 'APPROVED')
            max_seats       = ride.get('max_seats', 1)

            # Skip full rides
            if approved_count >= max_seats:
                continue

            # Skip if already a participant
            already_in = any(
                p.get('user_id') == user_oid for p in participants
            )
            if already_in:
                continue

            # ── STEP 4 — Route overlap ───────────────────
            ride_coords = decode_polyline(ride.get('route_polyline', ''))
            overlap     = route_overlap_pct(user_coords, ride_coords)
            if overlap < min_overlap_pct:
                continue

            # ── STEP 5 — Distance from $nearSphere ───────
            # MongoDB $nearSphere returns docs sorted by distance already.
            # Approximate distance using haversine of start_locations.
            ride_loc = ride['start_location']['coordinates']  # [lng, lat]
            dist_m   = haversine_m(
                user_location[1], user_location[0],
                ride_loc[1],      ride_loc[0],
            )

            # ── Enrich with creator info ─────────────────
            creator = users_col.find_one({'_id': ride['creator_id']})
            creator_name   = (creator or {}).get('full_name') or (creator or {}).get('phone', 'Unknown')
            creator_rating = (creator or {}).get('rating', 0.0)

            results.append({
                'ride_id':          str(ride['_id']),
                'creator_name':     creator_name,
                'creator_rating':   round(float(creator_rating), 1),
                'distance_meters':  round(dist_m),
                'available_seats':  max_seats - approved_count,
                'ride_time':        ride.get('ride_time', ''),
                'destination_name': ride.get('destination', {}).get('name', ''),
                '_sort_rating':     float(creator_rating),
            })

        # ── Rank: distance ASC  →  rating DESC ──────────
        results.sort(key=lambda r: (r['distance_meters'], -r['_sort_rating']))

        # Remove internal sort key before returning
        for r in results:
            r.pop('_sort_rating', None)

        print(f'[SEARCH] User {user_id} → {len(results)} match(es) on {ride_date}')
        return results
