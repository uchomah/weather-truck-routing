// RouteCard.jsx - one route's summary.

function fmtDuration(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.round((sec % 3600) / 60);
  return `${h}h ${m}m`;
}

function RouteCard({ route, recommended }) {
  const s = route.score;
  const status = s.has_no_travel ? "NO TRAVEL" : recommended ? "RECOMMENDED" : "alternative";

  return (
    <div className={`route-card ${recommended ? "recommended" : ""} ${s.has_no_travel ? "no-travel" : ""}`}>
      <div className="card-header">
        <span className="route-name">Route {route.index + 1}</span>
        <span className="status-badge">{status}</span>
      </div>
      <div className="card-stats">
        <div><span className="label">Distance</span><span>{route.distance_mi} mi</span></div>
        <div><span className="label">Drive time</span><span>{fmtDuration(route.duration_sec)}</span></div>
        <div><span className="label">Severe miles</span><span>{s.severe_miles} mi</span></div>
        <div><span className="label">High miles</span><span>{s.high_miles} mi</span></div>
        <div><span className="label">Avg risk</span><span>{s.avg_risk.toFixed(2)}</span></div>
      </div>
    </div>
  );
}

export default RouteCard;