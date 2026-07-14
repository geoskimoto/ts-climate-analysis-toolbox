import { useMemo } from 'react'
import { Plot, baseLayout, CONFIG } from '../plot'
import { INK, SERIES_BLUE, TREND } from '../palette'
import LazyChart from './LazyChart'

// Per-water-year scatter with the Mann-Kendall Sen's-slope line overlaid.
// A significant trend draws a solid colored line; otherwise a dashed gray line.
export default function TrendChart({ title, points, mk, yLabel, unit, hoverUnit, height = 300 }) {
  const { data, layout } = useMemo(
    () => build(points, mk, yLabel, unit, hoverUnit),
    [points, mk, yLabel, unit, hoverUnit],
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

function build(points, mk, yLabel, unit, hoverUnit) {
  const xs = points.map((p) => p.x)
  const ys = points.map((p) => p.y)
  const n = points.length
  const t = TREND[mk.trend] || TREND['no trend']

  // Sen's slope/intercept are indexed on position (0..n-1), matching the MK test.
  const fitX = [xs[0], xs[n - 1]]
  const fitY = [mk.intercept, mk.intercept + mk.slope * (n - 1)]

  const scatter = {
    type: 'scatter', x: xs, y: ys, mode: 'markers',
    marker: { color: SERIES_BLUE, size: 7, line: { color: '#fff', width: 1 } },
    name: yLabel,
    customdata: points.map((p) => p.label || ''),
    hovertemplate: `WY %{x}<br>%{y:.2f} ${hoverUnit || unit || ''}%{customdata}<extra></extra>`,
    showlegend: false,
  }
  const fit = {
    type: 'scatter', x: fitX, y: fitY, mode: 'lines',
    line: { color: mk.significant ? t.color : INK.muted, width: 2.5, dash: mk.significant ? 'solid' : 'dash' },
    name: 'Sen slope', hoverinfo: 'skip', showlegend: false,
  }

  const layout = baseLayout({
    margin: { l: 60, r: 16, t: 8, b: 40 },
    xaxis: { title: 'Water year', gridcolor: INK.grid, zeroline: false, linecolor: INK.grid },
    yaxis: { title: yLabel, gridcolor: INK.grid, zeroline: false },
    annotations: [
      {
        x: 1, y: 1.02, xref: 'paper', yref: 'paper', xanchor: 'right', yanchor: 'bottom',
        text: `${t.glyph} ${t.label} · ${mk.significant ? 'significant' : 'n.s.'} · p=${mk.p_value.toFixed(3)}`,
        showarrow: false, font: { size: 11, color: mk.significant ? t.color : INK.muted },
      },
    ],
  })
  return { data: [scatter, fit], layout }
}
