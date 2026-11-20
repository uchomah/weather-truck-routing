# services/weather.py - Open-Meteo calls. batched by design so we don't
# spam the API with one request per checkpoint.
#
# CHANGE: we now return a 48h hourly window per checkpoint, not just the
# hour at ETA. the frontend needs the whole window for the heatmap slider.

import requests
from datetime import datetime, timezone

OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"

MM_PER_INCH = 25.4
CM_PER_INCH = 2.54

BATCH_SIZE = 50

# how many hours of forecast to keep per checkpoint. spec says 0-48h slider.
FORECAST_HOURS = 48


def _fetch_batch(lats, lons):
    """one request for a batch of coords. returns parsed JSON."""
    params = {
        "latitude": ",".join(str(x) for x in lats),
        "longitude": ",".join(str(x) for x in lons),
        "hourly": "windspeed_10m,rain,showers,snowfall",
        "wind_speed_unit": "mph",
        "forecast_days": 3,  # need a bit more than 48h to be safe
        "timezone": "UTC",
    }

    resp = requests.get(OPEN_METEO_BASE, params=params, timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"open-meteo failed: {resp.status_code} {resp.text[:200]}")
    return resp.json()


def _extract_series(hourly):
    """
    pull the 4 hourly arrays out and convert units. returns a list of
    {time_iso, wind_mph, rain_in_hr, snow_in_hr} dicts, capped at FORECAST_HOURS.

    missing values stay None so the risk layer can flag them.
    """
    times = hourly.get("time") or []
    wind = hourly.get("windspeed_10m") or []
    rain = hourly.get("rain") or []
    showers = hourly.get("showers") or []
    snow = hourly.get("snowfall") or []

    series = []
    n = min(len(times), FORECAST_HOURS)

    for i in range(n):
        w = wind[i] if i < len(wind) else None

        # rain total = rain + showers, both mm/hr. to in/hr.
        r_raw = rain[i] if i < len(rain) else None
        s_raw = showers[i] if i < len(showers) else None
        if r_raw is not None and s_raw is not None:
            r = (r_raw + s_raw) / MM_PER_INCH
        elif r_raw is not None:
            r = r_raw / MM_PER_INCH
        else:
            r = None

        sn_raw = snow[i] if i < len(snow) else None
        sn = sn_raw / CM_PER_INCH if sn_raw is not None else None

        series.append({
            "time_iso": times[i],
            "wind_mph": w,
            "rain_in_hr": round(r, 3) if r is not None else None,
            "snow_in_hr": round(sn, 3) if sn is not None else None,
        })

    return series


def get_weather_for_checkpoints(checkpoints, departure_dt):
    """
    checkpoints: list from sampler, each has lon/lat/eta_offset_sec.
    departure_dt: tz-aware UTC datetime.

    returns a list of dicts, one per checkpoint, in the same order:
        {
          "eta_offset_sec": ...,
          "series": [ {time_iso, wind_mph, rain_in_hr, snow_in_hr}, ... ]  # 48 entries
        }
    """
    if not checkpoints:
        return []

    results = [None] * len(checkpoints)

    for start in range(0, len(checkpoints), BATCH_SIZE):
        batch = checkpoints[start:start + BATCH_SIZE]
        lats = [c["lat"] for c in batch]
        lons = [c["lon"] for c in batch]

        data = _fetch_batch(lats, lons)
        if isinstance(data, dict):
            data = [data]

        for i, cp in enumerate(batch):
            idx = start + i
            if i >= len(data):
                results[idx] = {"eta_offset_sec": cp["eta_offset_sec"], "series": []}
                continue

            hourly = data[i].get("hourly") or {}
            series = _extract_series(hourly)

            results[idx] = {
                "eta_offset_sec": cp["eta_offset_sec"],
                "series": series,
            }

    print(f"[weather] got series for {len(results)} checkpoints, "
          f"{FORECAST_HOURS}h each")
    return results