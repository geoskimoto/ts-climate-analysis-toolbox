import { useMemo } from 'react'
import { Plot, baseLayout, CONFIG } from '../plot'
import { INK, methodStyle } from '../palette'
import LazyChart from './LazyChart'

// Multi-method per-water-year chart: one marker series per method (distinct
// colour AND symbol) with its Sen's-slope line (solid if significant under the
// original MK test, dashed otherwise). Null metric values are gaps.
export default function BaseflowTrendChart({ title, methods, metricKey, yLabel, unit, height = 340 }) {
  const { data, layout } = useMemo(
    () => build(methods, metricKey, yLabel, unit),
    [methods, metricKey, yLabel, unit],
  )
  return (
    <figure className="chart">
      {title && <figcaption className="chart__title">{title}</figcaption>}
      <LazyChart height={height}>
        <Plot data={data} layout={layout} config={CONFIG} style={{ width: '100%', height }} useResizeHandler />
      </LazyChart>
    </figure>
  )
}

function build(methods, metricKey, yLabel, unit) {
  const data = []
  for (const m of methods) {
    const st = methodStyle(m.method)
    const xs = m.metrics.map((r) => r.water_year)
    const ys = m.metrics.map((r) => r[metricKey] ?? null)
    data.push({
      type: 'scatter', x: xs, y: ys, mode: 'lines+markers',
      connectgaps: false,
      line: { color: st.color, width: 1, dash: 'solid' },
      marker: { color: st.color, symbol: st.symbol, size: 7, line: { color: '#fff', width: 1 } },
      name: m.label,
      legendgroup: m.method,
      hovertemplate: `${m.label}<br>WY %{x}: %{y:.3g} ${unit}<extra></extra>`,
    })
    // Sen's slope is indexed over the non-null values in order (MK test input).
    const t = m.trends?.[metricKey]
    const valid = m.metrics.filter((r) => r[metricKey] != null)
    if (t && t.original && t.original.slope != null && t.original.intercept != null && valid.length >= 2) {
      const n = valid.length
      data.push({
        type: 'scatter', mode: 'lines',
        x: [valid[0].water_year, valid[n - 1].water_year],
        y: [t.original.intercept, t.original.intercept + t.original.slope * (n - 1)],
        line: { color: st.color, width: 2.5, dash: t.original.significant ? 'solid' : 'dash' },
        name: `${m.label} Sen slope`, legendgroup: m.method, showlegend: false,
        hovertemplate: `${m.label} Sen slope (${t.original.significant ? 'significant' : 'n.s.'})<extra></extra>`,
      })
    }
  }
  const layout = baseLayout({
    margin: { l: 64, r: 16, t: 8, b: 44 },
    legend: { orientation: 'h', x: 0, y: 1.12, font: { size: 11 } },
    xaxis: { title: 'Water year', gridcolor: INK.grid, zeroline: false, linecolor: INK.grid },
    yaxis: { title: `${yLabel} (${unit})`, gridcolor: INK.grid, zeroline: false },
  })
  return { data, layout }
}
