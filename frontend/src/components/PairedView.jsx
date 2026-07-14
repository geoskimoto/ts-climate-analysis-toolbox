import TrendChart from './TrendChart'

// The paired comparison: snowpack trends and streamflow trends over the same
// (co-registered) water-year window, plus the corroboration verdict.
const CATEGORY = {
  corroborating: { color: '#0ca30c', glyph: '✓', label: 'Corroborating' },
  mixed: { color: '#b9770e', glyph: '≠', label: 'Mixed' },
  inconclusive: { color: '#8a8984', glyph: '–', label: 'Inconclusive' },
}

export default function PairedView({ paired }) {
  const { gage, station, window, snow_trends, streamflow_trends, corroboration } = paired
  const cat = CATEGORY[corroboration.category] || CATEGORY.inconclusive
  const shortWindow = window.n_water_years < 20

  return (
    <div className="paired">
      <div className="paired__banner" style={{ borderColor: cat.color }}>
        <div className="paired__verdict" style={{ color: cat.color }}>
          <span className="paired__glyph">{cat.glyph}</span> {cat.label}
        </div>
        <p className="paired__summary">{corroboration.summary}</p>
        <ul className="paired__details">
          {corroboration.details.map((d, i) => <li key={i}>{d}</li>)}
        </ul>
      </div>

      <div className="paired__window">
        Shared record: <strong>WY {window.start_water_year}–{window.end_water_year}</strong>{' '}
        ({window.n_water_years} water years). Both signals are computed over this common window so
        they are directly comparable.
        {shortWindow && (
          <span className="paired__warn"> Short overlap — trends have limited statistical power.</span>
        )}
      </div>

      <section className="paired__domain">
        <h4>Snowpack — {station.name}</h4>
        <div className="chart-grid">
          {snow_trends.map((t) => <PairedTrend key={t.key} t={t} />)}
        </div>
      </section>

      <section className="paired__domain">
        <h4>Streamflow — {gage.name}</h4>
        <div className="chart-grid">
          {streamflow_trends.map((t) => <PairedTrend key={t.key} t={t} />)}
        </div>
      </section>
    </div>
  )
}

function PairedTrend({ t }) {
  if (!t.mk) {
    return <div className="chart placeholder">{t.label}: insufficient data over the shared window.</div>
  }
  const yLabel = t.kind === 'timing' ? `${t.label} (day of year)` : `${t.label} (${t.unit})`
  return (
    <TrendChart
      title={t.label}
      points={t.points.map((p) => ({ x: p.water_year, y: p.value }))}
      mk={t.mk}
      yLabel={yLabel}
      hoverUnit={t.kind === 'timing' ? 'day-of-yr' : t.unit}
    />
  )
}
