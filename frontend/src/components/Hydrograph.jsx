import { useMemo } from 'react'
import { Plot, baseLayout, CONFIG, WATER_YEAR_TICKS } from '../plot'
import { INK, IQR_FILL, SERIES_BLUE, yearColor, YEAR_RAMP } from '../palette'

// Daily hydrograph: every water year overlaid (colored old→new) on the
// day-of-year climatology envelope (median line + inter-quartile band).
export default function Hydrograph({ result }) {
  const { data, layout } = useMemo(() => build(result), [result])
  return (
    <figure className="chart">
      <figcaption className="chart__title">
        Daily hydrograph — all water years over the climatology envelope
      </figcaption>
      <Plot data={data} layout={layout} config={CONFIG} style={{ width: '100%', height: 360 }} useResizeHandler />
      <div className="year-legend">
        <span>{result.meta.water_years[0]}</span>
        <span className="year-legend__bar" style={{ background: `linear-gradient(90deg, ${YEAR_RAMP.join(',')})` }} />
        <span>{result.meta.water_years[result.meta.water_years.length - 1]}</span>
      </div>
    </figure>
  )
}

function build(result) {
  const { climatology, hydrograph, meta } = result
  const years = meta.water_years
  const yMin = years[0]
  const yMax = years[years.length - 1]
  const span = Math.max(1, yMax - yMin)

  const traces = []

  // Individual water years (drawn beneath the envelope). SVG scatter is used
  // rather than WebGL so the chart works on machines without GL support.
  for (const yr of hydrograph || []) {
    traces.push({
      type: 'scatter',
      x: yr.day_of_year,
      y: yr.value,
      mode: 'lines',
      line: { color: yearColor((yr.water_year - yMin) / span), width: 1 },
      opacity: 0.55,
      name: String(yr.water_year),
      hovertemplate: `WY ${yr.water_year} · %{y:.0f} ${meta.units}<extra></extra>`,
      showlegend: false,
    })
  }

  // Inter-quartile band (SVG, on top of the year lines).
  const dowy = climatology.map((c) => c.day_of_year)
  traces.push({
    type: 'scatter', x: dowy, y: climatology.map((c) => c.q75),
    mode: 'lines', line: { width: 0 }, hoverinfo: 'skip', showlegend: false,
  })
  traces.push({
    type: 'scatter', x: dowy, y: climatology.map((c) => c.q25),
    mode: 'lines', line: { width: 0 }, fill: 'tonexty', fillcolor: IQR_FILL,
    name: '25–75th pct', hoverinfo: 'skip', showlegend: true,
  })

  // Median climatology line.
  traces.push({
    type: 'scatter', x: dowy, y: climatology.map((c) => c.median),
    mode: 'lines', line: { color: INK.primary, width: 2.5 },
    name: 'Median', hovertemplate: `Median · %{y:.0f} ${meta.units}<extra></extra>`,
  })

  const layout = baseLayout({
    margin: { l: 60, r: 16, t: 8, b: 40 },
    legend: { orientation: 'h', x: 0, y: 1.08, font: { size: 11 } },
    xaxis: { ...WATER_YEAR_TICKS, gridcolor: INK.grid, zeroline: false, linecolor: INK.grid, range: [1, 366] },
    yaxis: { title: `${meta.value_label} (${meta.units})`, gridcolor: INK.grid, zeroline: false, rangemode: 'tozero' },
  })
  return { data: traces, layout }
}
