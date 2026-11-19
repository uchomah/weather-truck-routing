// RouteMap.jsx - the map. renders 3 route polylines + checkpoint dots.
// colors the polylines per-segment based on risk at the selected heatmap hour.

import { useEffect, useMemo } from "react";
import { MapContainer, TileLayer, Polyline, CircleMarker, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";

// colors per risk level. keyed to the strings the backend sends.
const RISK_COLORS = {
  LOW: "#2ecc71",
  MODERATE: "#f1c40f",
  HIGH: "#e67e22",
  SEVERE: "#e74c3c",
  NO_TRAVEL: "#000000",
};

// re-center the map when the trip data changes. leaflet doesn't auto-fit.
function Recenter({ bounds }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.length > 0) {
      map.fitBounds(bounds, { padding: [30, 30] });
    }
  }, [bounds, map]);
  return null;
}

function RouteMap({ tripData, heatmapHour }) {
  // build an overall bounding box from all routes' geometry
  const bounds = useMemo(() => {
    if (!tripData) return null;
    const all = [];
    for (const r of tripData.routes) {
      for (const c of r.geometry) {
        // geometry is [lon, lat], leaflet wants [lat, lon]
        all.push([c[1], c[0]]);
      }
    }
    return all.length ? all : null;
  }, [tripData]);

  if (!tripData) {
    return <div className="map-placeholder">Map will appear here once you plan a trip.</div>;
  }

  return (
    <MapContainer
      center={[42.0, -72.5]}  // rough center between NY and Boston
      zoom={7}
      className="route-map"
    >
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      {bounds && <Recenter bounds={bounds} />}

      {tripData.routes.map((route) => {
        // for each consecutive checkpoint pair, draw a colored segment.
        // the color is the risk of the LATER checkpoint (matches the
        // attribution rule we used in scoring).
        const segments = [];
        for (let i = 1; i < route.checkpoints.length; i++) {
          const prev = route.checkpoints[i - 1];
          const curr = route.checkpoints[i];

          // find weather at the selected slider hour for this checkpoint.
          // series is 48 entries; we clamp the index to whatever we have.
          const series = curr.series || [];
          const wx = series[Math.min(heatmapHour, series.length - 1)];

          // classify on the fly for the heatmap. we don't have load_lb here
          // in scope so we just use the base risk without load escalation -
          // good enough for the visual. real classification lives in the
          // backend and is what scoring uses.
          let risk = curr.risk;  // fallback to the ETA risk
          if (wx && wx.wind_mph != null) {
            risk = riskFromWeather(wx);
          }

          segments.push({
            key: `${route.index}-${i}`,
            positions: [
              [prev.lat, prev.lon],
              [curr.lat, curr.lon],
            ],
            color: RISK_COLORS[risk] || "#999",
          });
        }

        return (
          <div key={route.index}>
            {segments.map((s) => (
              <Polyline
                key={s.key}
                positions={s.positions}
                pathOptions={{ color: s.color, weight: route.index === tripData.recommended_index ? 6 : 3, opacity: 0.8 }}
              />
            ))}

            {route.checkpoints.map((cp, i) => (
              <CircleMarker
                key={`${route.index}-cp-${i}`}
                center={[cp.lat, cp.lon]}
                radius={4}
                pathOptions={{ color: RISK_COLORS[cp.risk] || "#999", fillOpacity: 0.9 }}
              >
                <Popup>
                  <div>
                    <strong>{cp.distance_mi} mi</strong><br />
                    ETA: {new Date(cp.eta_iso).toLocaleString()}<br />
                    Risk: {cp.risk}<br />
                    Wind: {cp.wind_mph ?? "?"} mph<br />
                    Rain: {cp.rain_in_hr ?? "?"} in/hr<br />
                    Snow: {cp.snow_in_hr ?? "?"} in/hr
                  </div>
                </Popup>
              </CircleMarker>
            ))}
          </div>
        );
      })}
    </MapContainer>
  );
}

// quick client-side risk classification for the heatmap visual only.
// mirrors the backend's base bands (no load escalation here).
function riskFromWeather(wx) {
  const w = wx.wind_mph ?? 0;
  const r = wx.rain_in_hr ?? 0;
  const s = wx.snow_in_hr ?? 0;

  if (w >= 55 || r > 1.0 || s > 3.0) return "NO_TRAVEL";
  if (w >= 45 || r > 0.50 || s > 2.0) return "SEVERE";
  if (w >= 35 || r > 0.25 || s > 1.0) return "HIGH";
  if (w >= 25 || r >= 0.10 || s >= 0.5) return "MODERATE";
  return "LOW";
}

export default RouteMap;