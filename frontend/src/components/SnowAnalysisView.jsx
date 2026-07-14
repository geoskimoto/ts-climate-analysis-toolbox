import MannKendallCard from './MannKendallCard'
import Hydrograph from './Hydrograph'
import TrendChart from './TrendChart'

// Right pane for a SNOTEL snow analysis. Reuses the shared Hydrograph and
// TrendChart (the response shares the streamflow climatology/hydrograph shape).
export default function SnowAnalysisView({ result }) {
  const { meta, peak_swe, april1_swe, melt_out } = result

  return (
    <div className="analysis">
      <header className="analysis__header">
        <h2>{meta.station.name}</h2>
        <div className="analysis__submeta">
          <span>SNOTEL {meta.station.station_triplet}</span>
          {meta.station.elevation_ft != null && <span>{fmt(meta.station.elevation_ft)} ft</span>}
          {meta.station.huc && <span>HUC {meta.station.huc}</span>}
          <span>{meta.record_start} – {meta.record_end}</span>
          <span>{meta.n_water_years} water years</span>
        </div>
        <div className="analysis__note">
          Snow water equivalent (SWE), inches. SNOTEL records are shorter (~1980–) than streamflow,
          so trends have less statistical power — read significance accordingly.
        </div>
      </header>

      <section className="mk-row">
        <MannKendallCard title="Peak SWE (magnitude)" mk={peak_swe.mk_magnitude} unit="in/yr"
          help="Trend in the annual maximum snow water equivalent. A decline is a warming signal." />
        <MannKendallCard title={`SWE on ${april1_swe.benchmark_month_day}`} mk={april1_swe.mk} unit="in/yr"
          help="Trend in snowpack on the benchmark date (default 1 April) — the classic water-supply index." />
        <MannKendallCard title="Peak SWE timing" mk={peak_swe.mk_timing} unit="days/yr"
          help="Trend in the day of year of peak snowpack." />
        <MeltOutCard melt={melt_out} />
      </section>

      <Hydrograph result={result} />

      <div className="chart-grid">
        <TrendChart
          title="Peak SWE trend"
          points={peak_swe.points.map((p) => ({ x: p.water_year, y: p.value }))}
          mk={peak_swe.mk_magnitude}
          yLabel="Peak SWE (in)"
          hoverUnit="in" />
        {april1_swe.mk ? (
          <TrendChart
            title={`SWE on ${april1_swe.benchmark_month_day} trend`}
            points={april1_swe.points.map((p) => ({ x: p.water_year, y: p.value }))}
            mk={april1_swe.mk}
            yLabel="SWE (in)"
            hoverUnit="in" />
        ) : (
          <div className="chart placeholder">No benchmark-date SWE available for this record.</div>
        )}
      </div>
    </div>
  )
}

function MeltOutCard({ melt }) {
  if (!melt.mk) {
    return (
      <div className="mk-card">
        <div className="mk-card__title">Melt-out date</div>
        <div className="mk-card__verdict" style={{ color: '#8a8984' }}>
          <span className="mk-card__trend" style={{ fontSize: 14 }}>insufficient data</span>
        </div>
      </div>
    )
  }
  return (
    <MannKendallCard title="Melt-out date" mk={melt.mk} unit="days/yr"
      help="Trend in the snow-disappearance date (first day SWE returns to zero after the peak). Earlier is a warming signal." />
  )
}

function fmt(n) {
  return Math.round(n).toLocaleString()
}
