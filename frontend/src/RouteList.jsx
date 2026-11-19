// RouteList.jsx - sidebar showing the 3 routes with scores.

import RouteCard from "./RouteCard";

function RouteList({ routes, recommendedIndex }) {
  if (!routes || routes.length === 0) {
    return <div className="route-list empty">No routes yet. Plan a trip.</div>;
  }

  return (
    <div className="route-list">
      <h3>Routes ({routes.length})</h3>
      {routes.map((r) => (
        <RouteCard key={r.index} route={r} recommended={r.index === recommendedIndex} />
      ))}
    </div>
  );
}

export default RouteList;