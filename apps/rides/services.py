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


# ── Downsample a polyline to ≤ ~1 point per `min_distance_m` ──
def downsample_coords(
    coords: list[tuple[float, float]],
    min_distance_m: float = 150.0,
) -> list[tuple[float, float]]:
    """
    Keep the first and last points always; drop intermediate points that are
    closer than `min_distance_m` to the last kept point. Bounds the cost of
    route_overlap_pct's nested loop to a small, roughly-fixed point count
    regardless of how detailed the source polyline is (OSRM/Google polylines
    can have hundreds of points for a multi-km route). Doesn't touch what's
    stored or shown on the map — only what's used for the overlap comparison.
    """
    if len(coords) <= 2:
        return coords

    kept = [coords[0]]
    last_lat, last_lng = coords[0]
    for lat, lng in coords[1:-1]:
        if haversine_m(last_lat, last_lng, lat, lng) >= min_distance_m:
            kept.append((lat, lng))
            last_lat, last_lng = lat, lng
    kept.append(coords[-1])
    return kept


# ── Route overlap (user_coords vs ride_coords) ────────────
def route_overlap_pct(
    user_coords: list[tuple[float, float]],
    ride_coords: list[tuple[float, float]],
    threshold_m: float = 150.0,
) -> float:
    """
    % of user route points that are within `threshold_m` of any ride point.
    Returns 0.0 if either list is empty (no polylines stored → skip filter).
    """
    if not user_coords or not ride_coords:
        return 100.0   # no polylines → don't reject on overlap

    user_coords = downsample_coords(user_coords)
    ride_coords = downsample_coords(ride_coords)

    matches = 0
    for ulat, ulng in user_coords:
        for rlat, rlng in ride_coords:
            if haversine_m(ulat, ulng, rlat, rlng) <= threshold_m:
                matches += 1
                break
    return (matches / len(user_coords)) * 100.0


# ── Time window (IST) ─────────────────────────────────────
def time_diff_minutes(time_a: str, time_b: str) -> int:
    """
    Absolute difference in minutes between two 'HH:MM' times, wrapping around
    midnight (e.g. 23:50 vs 00:10 → 20 min apart, not 1420).
    Returns a large number if either string is malformed, so the ride gets
    filtered out rather than accidentally matched.
    """
    try:
        h1, m1 = (int(p) for p in time_a.split(':')[:2])
        h2, m2 = (int(p) for p in time_b.split(':')[:2])
    except (ValueError, AttributeError):
        return 10_000
    total_a = h1 * 60 + m1
    total_b = h2 * 60 + m2
    diff = abs(total_a - total_b)
    return min(diff, 1440 - diff)


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
        gender_preference: str = 'Any',
    ) -> dict:
        rides = get_rides_collection()
        ride_doc = {
            'creator_id':        ObjectId(creator_id),
            'start_location':    start_location,
            'destination':       destination,
            'route_polyline':    route_polyline,
            'gender_preference': gender_preference,
            'ride_date':         ride_date,
            'ride_time':         ride_time,
            'max_seats':         max_seats,
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
        gender_filter:  str = 'All',     # Searching filter (All, Male, Female)
        search_time:    str = None,      # 'HH:MM' — when the searcher wants to travel
        time_window_minutes: int = 90,   # generous default: Indian trains/buses run late often
    ) -> list[dict]:
        """
        6-step matching pipeline (date/geo → exclusions → route overlap →
        time window → gender → rank).
        Returns a ranked list of ride dicts with enriched creator info.

        `time_window_minutes` defaults to a wide 90 minutes rather than a tight
        window, since Indian train/bus delays of 30-60+ minutes are routine —
        a strict window would filter out exactly the matches this app is meant
        to enable (someone already waiting for a commonly-late train).
        """
        from database.mongo import get_users_collection

        rides      = get_rides_collection()
        users_col  = get_users_collection()
        user_oid   = ObjectId(user_id)
        user_coords = decode_polyline(user_polyline)

        # Get searching user's gender
        searching_user = users_col.find_one({'_id': user_oid})
        searching_gender = (searching_user or {}).get('gender', 'Unknown')

        # ── STEP 1 + 2  Filter by date & 2km geo radius ──
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
                        '$maxDistance': 2000,  # metres
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

        # ── Pass 1: Filter candidates (Steps 3 & 4), collect survivors ──
        survivors = []
        for ride in candidates:

            # ── STEP 3 — Exclusions ──────────────────────
            if ride['creator_id'] == user_oid:
                continue

            participants   = ride.get('participants', [])
            approved_count = sum(1 for p in participants if p.get('status') == 'APPROVED')
            max_seats      = ride.get('max_seats', 1)

            if approved_count >= max_seats:
                continue

            already_in = any(p.get('user_id') == user_oid for p in participants)
            if already_in:
                continue

            # ── STEP 4 — Route overlap ───────────────────
            ride_coords = decode_polyline(ride.get('route_polyline', ''))
            if route_overlap_pct(user_coords, ride_coords) < min_overlap_pct:
                continue

            # ── STEP 4.5 — Time window ───────────────────
            # Only filter on time if the searcher gave a target time; otherwise
            # (e.g. browsing rides for the day generally) skip this check.
            ride_time_diff = 0
            if search_time:
                ride_time_diff = time_diff_minutes(search_time, ride.get('ride_time', ''))
                if ride_time_diff > time_window_minutes:
                    continue

            # Approximate distance using haversine of start_locations
            ride_loc = ride['start_location']['coordinates']  # [lng, lat]
            dist_m   = haversine_m(
                user_location[1], user_location[0],
                ride_loc[1],      ride_loc[0],
            )

            survivors.append({
                'ride':            ride,
                'approved_count':  approved_count,
                'max_seats':       max_seats,
                'dist_m':          dist_m,
                'time_diff':       ride_time_diff,
            })

        # ── Batch-fetch all creator docs in ONE query ────
        creator_oids = list({s['ride']['creator_id'] for s in survivors})
        creator_docs = users_col.find({'_id': {'$in': creator_oids}})
        creator_map  = {doc['_id']: doc for doc in creator_docs}

        # ── Pass 2: Gender check (Step 5) + build result list ──
        results = []
        for s in survivors:
            ride           = s['ride']
            approved_count = s['approved_count']
            max_seats      = s['max_seats']
            dist_m         = s['dist_m']
            time_diff      = s['time_diff']

            creator        = creator_map.get(ride['creator_id'], {})
            creator_name   = creator.get('full_name') or creator.get('phone', 'Unknown')
            creator_rating = creator.get('rating', 0.0)
            creator_gender = creator.get('gender', 'Unknown')

            # ── STEP 5 — Gender compatibility ────────────
            ride_pref = ride.get('gender_preference', 'Any')

            # 1. Does the CREATOR mandate a specific gender?
            if ride_pref != 'Any' and ride_pref != searching_gender:
                continue

            # 2. Does the SEARCHER mandate a specific gender?
            if gender_filter != 'All' and gender_filter != creator_gender:
                continue

            results.append({
                'ride_id':          str(ride['_id']),
                'creator_id':       str(ride['creator_id']),
                'creator_name':     creator_name,
                'creator_rating':   round(float(creator_rating), 1),
                'creator_gender':   creator_gender,
                'distance_meters':  round(dist_m),
                'time_diff_minutes': time_diff,
                'available_seats':  max_seats - approved_count,
                'ride_time':        ride.get('ride_time', ''),
                'destination_name': ride.get('destination', {}).get('name', ''),
                '_sort_rating':     float(creator_rating),
            })

        # ── Rank: time closeness ASC → distance ASC → rating DESC ──
        # Time compatibility comes first: two people can only share a ride if
        # they're leaving around the same time. Distance and rating are only
        # tiebreakers among rides that are already time-feasible.
        results.sort(key=lambda r: (r['time_diff_minutes'], r['distance_meters'], -r['_sort_rating']))

        for r in results:
            r.pop('_sort_rating', None)

        print(f'[SEARCH] User {user_id} → {len(results)} match(es) on {ride_date}')
        return results
