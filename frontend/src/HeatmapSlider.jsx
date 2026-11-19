// HeatmapSlider.jsx - the 0-48h forecast slider.
// lifts the selected hour up to App. RouteMap reads it to recolor the heatmap.

function HeatmapSlider({ hour, onChange, departureIso }) {
  // show what wall-clock time that hour offset lands on, so it's not just
  // a bare number. departure + hour.
  const label = (() => {
    if (!departureIso) return `+${hour}h`;
    const base = new Date(departureIso);
    const t = new Date(base.getTime() + hour * 3600 * 1000);
    return `+${hour}h  (${t.toUTCString().slice(5, 22)} UTC)`;
  })();

  return (
    <div className="heatmap-slider">
      <label>
        Forecast: <strong>{label}</strong>
        <input
          type="range"
          min="0"
          max="48"
          step="1"
          value={hour}
          onChange={(e) => onChange(Number(e.target.value))}
        />
      </label>
      <div className="slider-hint">
        drag to see how conditions along the corridor change over the next 48 hours
      </div>
    </div>
  );
}

export default HeatmapSlider;