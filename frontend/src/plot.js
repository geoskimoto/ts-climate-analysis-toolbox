// Build the React Plotly component against the lighter dist-min bundle.
import Plotly from 'plotly.js-dist-min'
import createPlotlyComponent from 'react-plotly.js/factory'
import { INK } from './palette'

export const Plot = createPlotlyComponent(Plotly)

// Shared layout defaults: transparent surface, recessive grid/axes, no chartjunk.
export function baseLayout(overrides = {}) {
  return {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    font: { family: 'system-ui, -apple-system, sans-serif', size: 12, color: INK.secondary },
    margin: { l: 56, r: 16, t: 12, b: 44 },
    hovermode: 'closest',
    xaxis: { gridcolor: INK.grid, zeroline: false, linecolor: INK.grid, tickcolor: INK.grid },
    yaxis: { gridcolor: INK.grid, zeroline: false, linecolor: INK.grid, tickcolor: INK.grid },
    ...overrides,
  }
}

export const CONFIG = { displayModeBar: false, responsive: true }

// October-first month ticks for the day-of-water-year axis (1 = Oct 1).
export const WATER_YEAR_TICKS = {
  tickvals: [1, 32, 62, 93, 124, 152, 183, 213, 244, 274, 305, 335],
  ticktext: ['Oct', 'Nov', 'Dec', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'],
}
