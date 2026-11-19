// TripForm.jsx - the input form. dumb component, just lifts state up to App.

function TripForm({ values, onChange, onSubmit, loading }) {
  const handle = (e) => {
    const { name, value } = e.target;
    onChange(name, value);
  };

  return (
    <form className="trip-form" onSubmit={(e) => { e.preventDefault(); onSubmit(); }}>
      <h2>Trip Planner</h2>

      <label>
        Origin
        <input type="text" name="origin" value={values.origin}
          onChange={handle} placeholder="e.g. New York, NY" required />
      </label>

      <label>
        Destination
        <input type="text" name="destination" value={values.destination}
          onChange={handle} placeholder="e.g. Boston, MA" required />
      </label>

      <label>
        Departure (UTC)
        <input type="datetime-local" name="departure" value={values.departure}
          onChange={handle} required />
      </label>

      <label>
        Load weight (lb)
        <input type="number" name="load_lb" value={values.load_lb}
          onChange={handle} min="0" step="1000" required />
      </label>

      <label>
        Sample interval
        <select name="interval_mi" value={values.interval_mi} onChange={handle}>
          <option value="10">every 10 miles</option>
          <option value="25">every 25 miles</option>
          <option value="50">every 50 miles</option>
        </select>
      </label>

      <button type="submit" disabled={loading}>
        {loading ? "Planning..." : "Plan trip"}
      </button>
    </form>
  );
}

export default TripForm;