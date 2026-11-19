# pipeline.py - orchestration. takes user input, returns routes with
# checkpoints, risk, ETAs, scores, recommendation, AND per-checkpoint
# 48h weather series so the frontend heatmap slider has data to scrub.

from datetime import datetime, timedelta, timezone

from routing.services.ors import geocode, get_three_routes
from routing.services.weather import get_weather_for_checkpoints
from routing.sampler import sample_route, METERS_PER_MILE
from routing.risk import classify_risk

RISK_INDEX = {"LOW": 0, "MODERATE": 1, "HIGH": 2, "SEVERE": 3, "NO_TRAVEL": 4}


def _legs_to_bounds(segments):
    bounds = []
    durations = []
    running = 0.0
    for seg in segments:
        running += seg["distance"]
        bounds.append(running)
        durations.append(seg["duration"])
    return bounds, durations


def _series_at_eta(series, departure_dt, eta_offset_sec):
    """
    pick the weather entry in the 48h series whose hour matches this
    checkpoint's ETA. floor to the hour, same rule as before.
    returns None if no match (forecast doesn't reach / series empty).
    """
    if not series:
        return None

    eta = departure_dt + timedelta(seconds=eta_offset_sec)
    target_hour = eta.replace(minute=0, second=0, microsecond=0)
    target_str = target_hour.strftime("%Y-%m-%dT%H:%M")

    for entry in series:
        if entry["time_iso"] == target_str:
            return entry
    return None


def _score_route(checkpoints, total_time_sec):
    severe_mi = 0.0
    high_mi = 0.0
    risk_sum = 0.0
    risk_count = 0
    has_no_travel = False

    for i, cp in enumerate(checkpoints):
        lvl = cp["risk"]
        if lvl == "NO_TRAVEL":
            has_no_travel = True
            lvl_for_score = "SEVERE"
        else:
            lvl_for_score = lvl

        if lvl != "NO_TRAVEL":
            risk_sum += RISK_INDEX[lvl]
            risk_count += 1

        if i > 0:
            seg_mi = cp["distance_mi"] - checkpoints[i - 1]["distance_mi"]
            if lvl_for_score == "SEVERE":
                severe_mi += seg_mi
            elif lvl_for_score == "HIGH":
                high_mi += seg_mi

    avg_risk = risk_sum / risk_count if risk_count else 0.0

    return {
        "severe_miles": round(severe_mi, 1),
        "high_miles": round(high_mi, 1),
        "avg_risk": round(avg_risk, 3),
        "total_time_sec": total_time_sec,
        "has_no_travel": has_no_travel,
    }


def _recommend(routes):
    eligible = [r for r in routes if not r["score"]["has_no_travel"]]
    if not eligible:
        return None

    def sort_key(r):
        s = r["score"]
        return (s["severe_miles"], s["high_miles"], s["avg_risk"], s["total_time_sec"])

    eligible.sort(key=sort_key)
    best = eligible[0]

    print(f"[pipeline] recommended route index {best['index']} "
          f"(severe {best['score']['severe_miles']} mi, "
          f"high {best['score']['high_miles']} mi, "
          f"avg risk {best['score']['avg_risk']})")

    return best["index"]


def build_trip(origin, destination, departure_dt, load_lb, interval_mi):
    print(f"[pipeline] trip {origin} -> {destination}, depart {departure_dt}, "
          f"load {load_lb} lb, interval {interval_mi} mi")

    # 1. geocode
    o_coords = geocode(origin)
    d_coords = geocode(destination)

    # 2. routes
    features = get_three_routes(o_coords, d_coords)

    # 3. sample
    per_route_cps = []
    flat_cps = []
    for f in features:
        coords = f["geometry"]["coordinates"]
        segments = f["properties"]["segments"]
        bounds, durations = _legs_to_bounds(segments)
        cps = sample_route(coords, bounds, durations, interval_mi)
        per_route_cps.append(cps)
        flat_cps.extend(cps)

    # 4. batch weather (now returns 48h series per checkpoint)
    weather = get_weather_for_checkpoints(flat_cps, departure_dt)

    # 5. slice per route, classify risk at ETA, carry the series through
    out_routes = []
    cursor = 0
    for idx, (f, cps) in enumerate(zip(features, per_route_cps)):
        n = len(cps)
        route_weather = weather[cursor:cursor + n]
        cursor += n

        summary = f["properties"]["summary"]

        enriched = []
        for cp, w in zip(cps, route_weather):
            series = w.get("series", [])
            at_eta = _series_at_eta(series, departure_dt, cp["eta_offset_sec"])

            if at_eta:
                risk = classify_risk(at_eta["wind_mph"], at_eta["rain_in_hr"],
                                     at_eta["snow_in_hr"], load_lb)
                unknown = (at_eta["wind_mph"] is None or
                           at_eta["rain_in_hr"] is None or
                           at_eta["snow_in_hr"] is None)
            else:
                # no weather found at this hour - treat as low + flag
                risk = "LOW"
                unknown = True

            eta = departure_dt + timedelta(seconds=cp["eta_offset_sec"])
            enriched.append({
                "lon": cp["lon"],
                "lat": cp["lat"],
                "distance_mi": round(cp["distance_mi"], 1),
                "eta_iso": eta.isoformat(),
                "wind_mph": at_eta["wind_mph"] if at_eta else None,
                "rain_in_hr": at_eta["rain_in_hr"] if at_eta else None,
                "snow_in_hr": at_eta["snow_in_hr"] if at_eta else None,
                "risk": risk,
                "unknown": unknown,
                # full 48h window - frontend heatmap uses this to recolor as slider moves
                "series": series,
            })

        score = _score_route(enriched, summary["duration"])

        out_routes.append({
            "index": idx,
            "distance_mi": round(summary["distance"] / METERS_PER_MILE, 1),
            "duration_sec": summary["duration"],
            "geometry": f["geometry"]["coordinates"],
            "checkpoints": enriched,
            "score": score,
        })

    recommended = _recommend(out_routes)

    return {
        "origin": {"name": origin, "lon": o_coords[0], "lat": o_coords[1]},
        "destination": {"name": destination, "lon": d_coords[0], "lat": d_coords[1]},
        "departure_iso": departure_dt.isoformat(),
        "load_lb": load_lb,
        "interval_mi": interval_mi,
        "routes": out_routes,
        "recommended_index": recommended,
    }