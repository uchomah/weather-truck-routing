# services/ors.py - all the openrouteservice calls live here.
# NOTE: base url is api.heigit.org now, not api.openrouteservice.org.
# the old one is deprecated and will shut off eventually.

import os
import math
import requests

ORS_BASE = "https://api.heigit.org"

# hgv profile so we route on truck-legal roads. we are NOT passing weight/height
# restrictions - without them ORS just ignores those tags. fine for our purposes
# since the assessment is about weather risk, not bridge clearances.
PROFILE = "driving-hgv"

# how far off the direct line to push the detour waypoint. tune this.
DETOUR_KM = 25


def _api_key():
    key = os.getenv("ORS_API_KEY")
    if not key:
        raise RuntimeError("ORS_API_KEY not set in .env")
    return key


def geocode(place):
    """
    turn a place name into (lon, lat).
    uses the pelias geocoding endpoint - note it lives under /pelias/v1 now,
    not under /openrouteservice. easy to get wrong.
    """
    url = f"{ORS_BASE}/pelias/v1/search"
    params = {
        "api_key": _api_key(),
        "text": place,
        "size": 1,  # just want the top hit
    }

    print(f"[ors] geocoding: {place}")

    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"geocode failed for '{place}': {resp.status_code} {resp.text[:200]}")

    data = resp.json()
    features = data.get("features") or []
    if not features:
        raise RuntimeError(f"no geocode result for '{place}'")

    # pelias returns geojson. coords are [lon, lat]
    lon, lat = features[0]["geometry"]["coordinates"]
    print(f"[ors]   -> ({lon}, {lat})")
    return lon, lat


def get_routes(origin_coords, dest_coords, target_count=3):
    """
    ask for up to `target_count` alternative routes between two (lon, lat) points.
    returns the raw list of route objects from ORS - caller slices what it needs.

    NOTE: ORS does not guarantee it gives you the count you asked for.
    if the road network is sparse it might only return 1 or 2. handle upstream.
    ALSO NOTE: public tier caps alternative_routes at 100 km. this function
    will 400 on longer trips. use get_three_routes() instead.
    """
    url = f"{ORS_BASE}/openrouteservice/v2/directions/{PROFILE}/geojson"

    body = {
        "coordinates": [list(origin_coords), list(dest_coords)],
        "alternative_routes": {
            "target_count": target_count,
            # share_factor: how much overlap is allowed between alternatives.
            # 0.6 is the ORS default-ish, lets routes diverge meaningfully.
            "share_factor": 0.6,
            "weight_factor": 1.4,
        },
    }

    headers = {
        "Authorization": _api_key(),
        "Content-Type": "application/json",
    }

    print(f"[ors] routing {origin_coords} -> {dest_coords}, want {target_count} routes")

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"routing failed: {resp.status_code} {resp.text[:300]}")

    data = resp.json()
    features = data.get("features") or []
    print(f"[ors]   -> got {len(features)} route(s)")

    # geojson features. each has properties.summary + geometry.coordinates
    # and properties.segments (the legs). we hand back the features list.
    return features


# ---- detour synthesis ----
# ORS caps alternative_routes at 100 km on the public tier, so we can't ask
# for 3 routes on a real trip. instead we get the direct route, then push a
# waypoint off to each side and re-route. gives us 2 genuinely different paths.


def _midpoint_and_bearing(coords):
    """find midpoint of the route geometry and the bearing there."""
    mid_idx = len(coords) // 2
    mid = coords[mid_idx]
    a = coords[max(0, mid_idx - 1)]
    b = coords[min(len(coords) - 1, mid_idx + 1)]

    lon1, lat1 = math.radians(a[0]), math.radians(a[1])
    lon2, lat2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1

    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    bearing = math.atan2(x, y)  # radians, 0 = north
    return mid, bearing


def _offset_point(lon, lat, bearing_rad, offset_km, side, angle_rad=None):
    """
    push a point off the bearing line. angle_rad is how far off perpendicular
    to push (default = exactly perpendicular). side flips left/right.
    flat-earth approx, fine for offsets under ~50 km.
    """
    if angle_rad is None:
        angle_rad = math.pi / 2  # 90 degrees, straight perpendicular

    # push angle is bearing +/- the offset angle
    push_bearing = bearing_rad + side * angle_rad

    dlat = (offset_km / 111.0) * math.cos(push_bearing)
    dlon = (offset_km / (111.0 * math.cos(math.radians(lat)))) * math.sin(push_bearing)
    return [lon + dlon, lat + dlat]


def _post_route(coord_list):
    """post a coord list to the directions endpoint, no alternatives. returns first feature."""
    url = f"{ORS_BASE}/openrouteservice/v2/directions/{PROFILE}/geojson"
    body = {"coordinates": [list(c) for c in coord_list]}
    headers = {"Authorization": _api_key(), "Content-Type": "application/json"}

    resp = requests.post(url, json=body, headers=headers, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"route failed: {resp.status_code} {resp.text[:200]}")

    features = resp.json().get("features") or []
    return features[0] if features else None


def get_three_routes(origin_coords, dest_coords):
    """
    direct route + 2 detour variants. drops detours that are within 2%
    of the direct distance (too similar to count as an alternative).

    detour points can land in water or off-road (NY->Boston side=+1 hits
    Long Island Sound at 25km). so we retry smaller offsets, and if straight
    perpendicular keeps failing, try a diagonal push before giving up.
    """
    direct = _post_route([origin_coords, dest_coords])
    if not direct:
        raise RuntimeError("could not get direct route")

    routes = [direct]
    direct_dist = direct["properties"]["summary"]["distance"]

    coords = direct["geometry"]["coordinates"]
    mid, bearing = _midpoint_and_bearing(coords)

    OFFSETS_KM = [25, 15, 8]
    ANGLES_DEG = [90, 45]  # 90 = straight perpendicular, 45 = diagonal

    for side in (+1, -1):
        leg = None
        for angle_deg in ANGLES_DEG:
            for offset_km in OFFSETS_KM:
                angle_rad = math.radians(angle_deg)
                detour_pt = _offset_point(mid[0], mid[1], bearing, offset_km, side, angle_rad)
                try:
                    leg = _post_route([origin_coords, detour_pt, dest_coords])
                    print(f"[ors] detour side={side} angle={angle_deg} offset={offset_km}km ok")
                    break  # got one, stop trying smaller offsets
                except RuntimeError as e:
                    print(f"[ors] detour side={side} angle={angle_deg} offset={offset_km}km failed: {str(e)[:80]}")
                    leg = None
                    continue
            if leg:
                break  # got one at this angle, no need to try diagonal

        if not leg:
            print(f"[ors] detour side={side} gave up after all offsets/angles")
            continue

        detour_dist = leg["properties"]["summary"]["distance"]
        if abs(detour_dist - direct_dist) / direct_dist < 0.02:
            print(f"[ors] detour side={side} too similar ({detour_dist:.0f}m vs {direct_dist:.0f}m), dropping")
            continue

        print(f"[ors] detour side={side} kept: {detour_dist/1000:.0f} km vs direct {direct_dist/1000:.0f} km")
        routes.append(leg)

    print(f"[ors] returning {len(routes)} route(s)")
    return routes