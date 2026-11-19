# views.py - the one endpoint the frontend hits.

from datetime import datetime, timezone

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from routing.pipeline import build_trip


@api_view(["POST"])
def route_view(request):
    """
    POST body:
      {
        "origin": "New York, NY",
        "destination": "Boston, MA",
        "departure": "2026-11-18T12:00:00Z",   # ISO, UTC
        "load_lb": 20000,
        "interval_mi": 25
      }
    """
    data = request.data

    # validate the bare minimum. ugly but gets the job done.
    missing = [f for f in ("origin", "destination", "departure", "load_lb", "interval_mi")
               if f not in data]
    if missing:
        return Response({"error": f"missing fields: {missing}"}, status=status.HTTP_400_BAD_REQUEST)

    if data["interval_mi"] not in (10, 25, 50):
        return Response({"error": "interval_mi must be 10, 25, or 50"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        departure_dt = datetime.fromisoformat(data["departure"].replace("Z", "+00:00"))
        if departure_dt.tzinfo is None:
            departure_dt = departure_dt.replace(tzinfo=timezone.utc)
    except Exception:
        return Response({"error": "departure must be ISO datetime"},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        result = build_trip(
            origin=data["origin"],
            destination=data["destination"],
            departure_dt=departure_dt,
            load_lb=float(data["load_lb"]),
            interval_mi=int(data["interval_mi"]),
        )
        return Response(result)
    except Exception as e:
        # don't leak stack traces to the client. log server side later.
        print(f"[view] pipeline blew up: {e}")
        return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)