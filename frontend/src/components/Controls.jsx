// Analysis parameter controls. Local state mirrors the request; "Run analysis"
// pushes it up so a fetch only fires on explicit submit (or the initial load).
export default function Controls({ params, setParams, onRun, running }) {
  const set = (k) => (e) => {
    const v = e.target.type === 'checkbox' ? e.target.checked : e.target.value
    setParams({ ...params, [k]: v })
  }
  return (
    <form
      className="controls"
      onSubmit={(e) => {
        e.preventDefault()
        onRun()
      }}
    >
      <label className="field">
        <span>Start</span>
        <input className="input" type="date" value={params.start_date} onChange={set('start_date')} />
      </label>
      <label className="field">
        <span>End</span>
        <input className="input" type="date" value={params.end_date} onChange={set('end_date')} />
      </label>
      <label className="field field--sm">
        <span>Timing %</span>
        <input className="input" type="number" min="0.1" max="0.9" step="0.05"
          value={params.threshold_percent} onChange={set('threshold_percent')} />
      </label>
      <label className="field field--sm">
        <span>α</span>
        <input className="input" type="number" min="0.01" max="0.5" step="0.01"
          value={params.alpha} onChange={set('alpha')} />
      </label>
      <label className="field field--sm">
        <span>Peak window (d)</span>
        <input className="input" type="number" min="1" max="60" step="1"
          value={params.peak_window_size} onChange={set('peak_window_size')} />
      </label>
      <label className="field field--check">
        <input type="checkbox" checked={params.ignore_winter_months} onChange={set('ignore_winter_months')} />
        <span>Ignore winter peaks</span>
      </label>
      <button className="btn" type="submit" disabled={running}>
        {running ? 'Running…' : 'Run analysis'}
      </button>
    </form>
  )
}
