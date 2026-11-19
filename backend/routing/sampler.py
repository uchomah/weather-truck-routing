# sampler.py - walk a route geometry and drop a checkpoint every N miles.
# also has to know the ETA (cumulative duration) at each checkpoint, because
# weather has to be looked up at the time the truck actually gets there.

import math

METERS_PER_MILE = 1609.344

# earth radius in meters, for the haversine distance between geometry points
R_EARTH_M = 6371000.0


def haversine_m(a, b):
    """
    distance in meters between two (lon, lat) points.
    ORS gives us lon,lat order so both args are (lon, lat).
    """
    lon1, lat1 = a
    lon2, lat2 = b

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)

    h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R_EARTH_M * math.asin(math.sqrt(h))


def build_cumulative_distances(coords):
    """
    given a list of (lon, lat), return cumulative meters at each point.
    cum[0] is always 0. cum[i] is meters traveled to reach coords[i].
    """
    cum = [0.0]
    for i in range(1, len(coords)):
        d = haversine_m(coords[i - 1], coords[i])
        cum.append(cum[-1] + d)
    return cum


def duration_at_distance(target_m, leg_bounds, leg_durations):
    """
    interpolate cumulative duration (seconds) at a given distance along the route.

    leg_bounds: cumulative meters at the end of each ORS leg, e.g. [5000, 12000, 20000]
    leg_durations: duration in seconds for each leg, e.g. [400, 800, 900]

    this is the ugly part - legs and geometry points dont line up 1:1, so we
    just find which leg bucket the target distance falls in and lerp inside it.
    good enough for ETA purposes, we're not doing rocket surgery here.
    """
    # walk up the legs until we find the bucket
    prev_bound = 0.0
    prev_time = 0.0
    for i, bound in enumerate(leg_bounds):
        if target_m <= bound:
            leg_dist = bound - prev_bound
            if leg_dist <= 0:
                # degenerate leg, avoid divide by zero. just give it the leg duration.
                return prev_time + leg_durations[i]
            frac = (target_m - prev_bound) / leg_dist
            return prev_time + frac * leg_durations[i]
        prev_time += leg_durations[i]
        prev_bound = bound

    # past the end - shouldn't happen if bounds are right, but clamp anyway
    return prev_time


def sample_route(coords, leg_bounds, leg_durations, interval_mi):
    """
    the main entry point. returns a list of checkpoints:
        [{lon, lat, distance_mi, eta_offset_sec}, ...]

    always includes the start and the end, regardless of interval.
    interval_mi is 10, 25, or 50 - caller picks.
    """
    if not coords or len(coords) < 2:
        return []

    interval_m = interval_mi * METERS_PER_MILE
    cum = build_cumulative_distances(coords)
    total_m = cum[-1]

    # which distances along the route do we want to sample?
    # start at 0, step by interval, always include the endpoint.
    wanted = [0.0]
    d = interval_m
    while d < total_m:
        wanted.append(d)
        d += interval_m
    if total_m > 0:
        wanted.append(total_m)

    checkpoints = []

    # for each wanted distance, find the geometry point closest to it.
    # NOTE: this is O(n*m) and could be a two-pointer scan, but routes are
    # a few thousand points at most and readability matters more right now.
    for target in wanted:
        # find the first cum value >= target
        idx = 0
        for i, c in enumerate(cum):
            if c >= target:
                idx = i
                break
        else:
            idx = len(coords) - 1

        lon, lat = coords[idx]
        eta_sec = duration_at_distance(target, leg_bounds, leg_durations)

        checkpoints.append({
            "lon": lon,
            "lat": lat,
            "distance_mi": target / METERS_PER_MILE,
            "eta_offset_sec": eta_sec,
        })

    print(f"[sampler] {len(checkpoints)} checkpoints, total {total_m / METERS_PER_MILE:.1f} mi, "
          f"interval {interval_mi} mi")

    return checkpoints