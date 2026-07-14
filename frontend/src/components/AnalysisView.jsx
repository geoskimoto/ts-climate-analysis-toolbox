import { useState } from 'react'
import MannKendallCard from './MannKendallCard'
import Hydrograph from './Hydrograph'
import TrendChart from './TrendChart'
import PairingPanel from './PairingPanel'

// Right pane once an analysis has run: site header, verdict cards, the
// hydrograph, and the per-year trend charts.
export default function AnalysisView({ result }) {
  const { meta, center_of_timing, total_volume, seasonal_volumes, peak } = result
  const [windowIdx, setWindowIdx] = useState(seasonal_volumes.length - 1) // default: last window (summer)
  const win = seasonal_volumes[windowIdx]

  const summer = seasonal_volumes.find((w) => /summer/i.test(w.label)) || seasonal_volumes[seasonal_volumes.length - 1]

  return (
    <div className="analysis">
      <header className="analysis__header">
        <h2>{meta.site.name}</h2>
        <div className="analysis__submeta">
          <span>USGS {meta.site.site_no}</span>
          {meta.site.drainage_area_sqmi != null && <span>{fmt(meta.site.drainage_area_sqmi)} sq mi</span>}
          {meta.site.elevation_ft != null && <span>{fmt(meta.site.elevation_ft)} ft</span>}
          <span>{meta.record_start} – {meta.record_end}</span>
          <span>{meta.n_water_years} water years</span>
        </div>
      </header>

      <section className="mk-row">
        <MannKendallCard
          title={`Center of timing (${Math.round(center_of_timing.threshold_percent * 100)}%)`}
          mk={center_of_timing.mk_timing} unit="days/yr"
          help="Trend in the day of year when half the annual runoff has passed. Earlier over time is the classic snowmelt-warming signal." />
        <MannKendallCard title="Total annual volume" mk={total_volume.mk} unit="maf/yr"
          help="Trend in total annual runoff volume (million acre-feet)." />
        <MannKendallCard title={summer.label + ' volume'} mk={summer.mk} unit="maf/yr"
          help="Trend in warm-season runoff volume — sensitive to snow→rain regime shifts." />
        <MannKendallCard title="Peak timing" mk={peak.mk_timing} unit="days/yr"
          help="Trend in the day of year of the annual peak flow." />
      </section>

      <Hydrograph result={result} />

      <div className="chart-grid">
        <TrendChart
          title="Center-of-timing trend"
          points={center_of_timing.points.map((p) => ({ x: p.water_year, y: p.day_of_year, label: ` (${p.month_day})` }))}
          mk={center_of_timing.mk_timing}
          yLabel="Day of water year"
          hoverUnit="day-of-yr" />

        <div>
          <div className="chart__select-row">
            <label>Seasonal window&nbsp;
              <select className="input input--select" value={windowIdx} onChange={(e) => setWindowIdx(Number(e.target.value))}>
                {seasonal_volumes.map((w, i) => <option key={i} value={i}>{w.label}</option>)}
              </select>
            </label>
          </div>
          <TrendChart
            points={win.points.map((p) => ({ x: p.water_year, y: p.volume_maf }))}
            mk={win.mk}
            yLabel="Volume (maf)"
            hoverUnit="maf" />
        </div>
      </div>

      <PairingPanel siteNo={meta.site.site_no} />
    </div>
  )
}

function fmt(n) {
  return Math.round(n).toLocaleString()
}
