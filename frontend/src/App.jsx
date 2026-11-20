// App.jsx - top-level. owns state, calls the API, lays out the page.

import { useState } from "react";
import axios from "axios";
import TripForm from "./TripForm";
import RouteList from "./RouteList";
import RouteMap from "./RouteMap";
import HeatmapSlider from "./HeatmapSlider";
import "./App.css";

const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000/api";

// initial form values. departure defaults to now-ish, rounded to the hour,
// formatted for datetime-local (no Z, no timezone).
function initialFormState() {
  const now = new Date();
  now.setMinutes(0, 0, 0);
  // toISOString gives "...Z", datetime-local wants "YYYY-MM-DDTHH:MM"
  const local = now.toISOString().slice(0, 16);
  return {
    origin: "New York, NY",
    destination: "Boston, MA",
    departure: local,
    load_lb: 20000,
    interval_mi: 25,
  };
}

function App() {
  const [form, setForm] = useState(initialFormState);
  const [tripData, setTripData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [heatmapHour, setHeatmapHour] = useState(0);

  const handleChange = (name, value) => {
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      // datetime-local gives us no timezone. the backend wants ISO with one.
      // append Z to treat it as UTC. this is a known simplification - if the
      // user's local timezone isn't UTC, departure will be off. flagging it.
      const departureIso = form.departure.length === 16
        ? form.departure + ":00Z"
        : form.departure;

      const payload = {
        origin: form.origin,
        destination: form.destination,
        departure: departureIso,
        load_lb: Number(form.load_lb),
        interval_mi: Number(form.interval_mi),
      };

      console.log("[app] posting", payload);

      const res = await axios.post(`${API_BASE}/route/`, payload, { timeout: 120000 });
      console.log("[app] got response, routes:", res.data.routes?.length);

      setTripData(res.data);
      setHeatmapHour(0);  // reset slider on new trip
    } catch (e) {
      console.error("[app] error:", e);
      const msg = e.response?.data?.error || e.message || "request failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="app-header">
        <h1>Weather-Aware Truck Routing</h1>
        <p className="subtitle">pick a route, see the weather risk along the way</p>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <TripForm
            values={form}
            onChange={handleChange}
            onSubmit={handleSubmit}
            loading={loading}
          />
          {error && <div className="error-box">Error: {error}</div>}
          {tripData && (
            <RouteList
              routes={tripData.routes}
              recommendedIndex={tripData.recommended_index}
            />
          )}
        </aside>

        <main className="main-panel">
          {tripData ? (
            <>
              <RouteMap tripData={tripData} heatmapHour={heatmapHour} />
              <HeatmapSlider
                hour={heatmapHour}
                onChange={setHeatmapHour}
                departureIso={tripData.departure_iso}
              />
            </>
          ) : (
            <div className="map-placeholder">
              {loading ? "Planning trip..." : "Enter a trip and click Plan trip to see the map."}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;