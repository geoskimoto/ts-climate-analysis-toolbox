import { useMemo } from 'react'
import { Plot, baseLayout, CONFIG } from '../plot'
import { INK, methodStyle } from '../palette'
import LazyChart from './LazyChart'

// One water year: observed flow (solid dark) with each method's baseflow in
// its own colour and dash style.
export default function BaseflowHydrograph({ example, methods }) {
  const { data, layout } = useMemo(() => build(example, methods), [example, methods])
  return (
    <figure className="chart">
      <figcaption className="chart__title">
        Example hydrograph — water year {example.water_year}: observed flow and separated baseflow
      </figcaption>
      <LazyChart height={340}>
        <Plot data={data} layout={layout} config={CONFIG} style={{ width: '100%', height: 340 }} useResizeHandler />
      </LazyChart>
    </figure>
  )
}

function build(example, methods) {
  const label = Object.fromEntries(methods.map((m) => [m.method, m.label]))
  const data = [{
    type: 'scatter', mode: 'lines', x: example.dates, y: example.flow_cfs,
    line: { color: INK.primary, width: 1.6, dash: 'solid' }, connectgaps: false,
    name: 'Observed flow', hovertemplate: 'Observed %{y:.0f} cfs<br>%{x}<extra></extra>',
  }]
  for (const [m, ys] of Object.entries(example.baseflow_cfs)) {
    const st = methodStyle(m)
    const nm = label[m] || m
    data.push({
      type: 'scatter', mode: 'lines', x: example.dates, y: ys, connectgaps: false,
      line: { color: st.color, width: 2.2, dash: st.dash },
      name: `${nm} baseflow`, hovertemplate: `${nm} %{y:.0f} cfs<br>%{x}<extra></extra>`,
    })
  }
  const layout = baseLayout({
    margin: { l: 64, r: 16, t: 8, b: 44 },
    legend: { orientation: 'h', x: 0, y: 1.14, font: { size: 11 } },
    xaxis: { title: 'Date', type: 'date', gridcolor: INK.grid, zeroline: false, linecolor: INK.grid },
    yaxis: { title: 'Discharge (cfs)', gridcolor: INK.grid, zeroline: false, rangemode: 'tozero' },
  })
  return { data, layout }
}
