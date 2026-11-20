
# Weather-Aware Truck Routing

A full-stack web app that helps a truck driver pick the safest route based on weather, load weight, and travel time.

**Live:** https://weather-truck-routing-olive.vercel.app/

## What it does

Enter an origin, destination, departure time, and load weight. The app:

1. Generates up to 3 route options via OpenRouteService (truck profile `driving-hgv`).
2. Samples weather every 10 / 25 / 50 miles along each route, at the ETA for each checkpoint.
3. Classifies weather risk at each checkpoint against the spec's wind/rain/snow thresholds.
4. Applies load-weight escalation rules (heavy loads escalate wind risk to Severe or No Travel).
5. Scores each route and recommends one using a 4-tier priority:
   - Fewest Severe miles
   - Fewest High miles
   - Lowest average risk
   - Shortest travel time
6. Shows all routes, checkpoints, risk levels, ETAs, and summaries on a Leaflet map.
7. Provides a 0–48 hour forecast slider that recolors the corridor heatmap over time.

## Stack

- **Backend:** Django 5.2 + Django REST Framework, Python 3.14
- **Frontend:** React 18 + Vite, Leaflet for maps
- **Routing/geocoding:** OpenRouteService (free tier)
- **Weather:** Open-Meteo (free, no key)

## Architecture

```text
frontend (Vercel) --POST /api/route/--> backend (Render)
                                          |
                                          +--> ORS: geocode + routing
                                          +--> Open-Meteo: 48h hourly weather
                                          +--> risk / scoring / recommendation
```

The backend is stateless. No database is required (SQLite exists in settings only for Django's defaults).

## Backend structure

```text
backend/routing/
    risk.py          # Risk classification (wind/rain/snow + load rules)
    sampler.py       # Checkpoint sampling along route geometry
    pipeline.py      # Orchestration: geocode -> route -> sample -> weather -> score -> recommend
    services/
        ors.py       # Geocoding + routing (direct route + 2 detours)
        weather.py   # Batched Open-Meteo fetches with 48h series per checkpoint
    tests/
        test_risk.py # Risk table boundary tests + load escalation tests
        test_sampler.py
    views.py         # POST /api/route/
    urls.py
```

## Running locally

### Backend

```bash
cd backend

python -m venv venv

# Windows:
venv\Scripts\activate

# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# Create backend/.env with:
# ORS_API_KEY=your-openrouteservice-key
# DEBUG=True

python manage.py runserver
```

The backend runs at `http://127.0.0.1:8000`.

### Frontend

```bash
cd frontend

npm install
npm run dev
```

The frontend runs at `http://localhost:5173` and calls the backend at `http://127.0.0.1:8000/api` by default.

Override with `VITE_API_BASE` in `frontend/.env.local`:

```text
VITE_API_BASE=http://127.0.0.1:8000/api
```

## API

`POST /api/route/`

### Request

```json
{
  "origin": "New York, NY",
  "destination": "Boston, MA",
  "departure": "2026-11-20T12:00:00Z",
  "load_lb": 20000,
  "interval_mi": 25
}
```

### Response

```json
{
  "origin": {
    "name": "...",
    "lon": -73.97,
    "lat": 40.68
  },
  "destination": {
    "name": "...",
    "lon": -71.04,
    "lat": 42.35
  },
  "departure_iso": "2026-11-20T12:00:00+00:00",
  "load_lb": 20000,
  "interval_mi": 25,
  "routes": [
    {
      "index": 0,
      "distance_mi": 218.3,
      "duration_sec": 15925.5,
      "geometry": [
        [-73.97, 40.68],
        [-71.04, 42.35]
      ],
      "checkpoints": [
        {
          "lon": -73.97,
          "lat": 40.68,
          "distance_mi": 0.0,
          "eta_iso": "2026-11-20T12:00:00+00:00",
          "wind_mph": 5.6,
          "rain_in_hr": 0.0,
          "snow_in_hr": 0.0,
          "risk": "LOW",
          "unknown": false,
          "series": [
            {
              "time_iso": "2026-11-20T12:00",
              "wind_mph": 5.6,
              "rain_in_hr": 0.0,
              "snow_in_hr": 0.0
            }
          ]
        }
      ],
      "score": {
        "severe_miles": 0.0,
        "high_miles": 0.0,
        "avg_risk": 0.0,
        "total_time_sec": 15925.5,
        "has_no_travel": false
      }
    }
  ],
  "recommended_index": 0
}
```

## Design notes

- **Route synthesis:** ORS caps `alternative_routes` at 100 km on the public tier, so long trips can't use it. Instead, `get_three_routes` gets the direct route, then pushes a waypoint 25 / 15 / 8 km off the direct line on each side. Detours that fail (e.g. land in water) retry smaller, then try a diagonal push. Detours within 2% of the direct route's distance are dropped (too similar to be a real alternative).
- **Risk attribution:** The segment from checkpoint `i-1` to checkpoint `i` takes checkpoint `i`'s risk. No-Travel checkpoints count toward Severe miles for ranking but are excluded from the average.
- **Weather granularity:** ETAs are floored to the hour; the Open-Meteo hourly bucket matching that hour is used. Checkpoints whose ETA falls outside the forecast window are flagged `unknown` and treated as Low for scoring.
- **Units:** One `METERS_PER_MILE` constant, mm-to-in and cm-to-in conversions in `weather.py`. Wind requested in mph directly from Open-Meteo.
- **No-Travel routes:** Shown but excluded from the recommendation. If all three routes are No-Travel, `recommended_index` is `null`.

## Known limitations

- ORS public tier: 2,000 routing requests/day, 40/min.
- Render free tier spins down after inactivity; first request after idle takes approximately 50 seconds.
- Departure time is treated as UTC (`datetime-local` input has no timezone; `App.jsx` appends `Z`).

## Tests

```bash
cd backend
python manage.py test routing.tests
```

Covers the risk table boundaries, load escalation, and the sampler's checkpoint spacing.
