// Analysis parameter controls for SNOTEL snow analysis.
export default function SnowControls({ params, setParams, onRun, running }) {
  const set = (k) => (e) => setParams({ ...params, [k]: e.target.value })
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
        <span>Benchmark date</span>
        <input className="input" type="text" pattern="\d{2}-\d{2}" placeholder="04-01"
          value={params.benchmark_month_day} onChange={set('benchmark_month_day')} />
      </label>
      <label className="field field--sm">
        <span>α</span>
        <input className="input" type="number" min="0.01" max="0.5" step="0.01"
          value={params.alpha} onChange={set('alpha')} />
      </label>
      <button className="btn" type="submit" disabled={running}>
        {running ? 'Running…' : 'Run analysis'}
      </button>
    </form>
  )
}
