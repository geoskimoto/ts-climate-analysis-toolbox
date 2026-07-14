// Chart palette — validated default from the dataviz method (light mode).
// Trend direction uses a diverging blue↔red pair by the sign of the slope;
// "no trend" is neutral gray. Direction is always paired with an arrow glyph,
// so meaning is never color-alone.

export const INK = {
  primary: '#0b0b0b',
  secondary: '#52514e',
  muted: '#8a8984',
  grid: '#e8e7e3',
  surface: '#fcfcfb',
}

export const SERIES_BLUE = '#2a78d6'
export const IQR_FILL = 'rgba(42, 120, 214, 0.14)'

// Sequential blue ramp (light→dark) used to color water years old→new.
export const YEAR_RAMP = [
  '#cde2fb', '#9ec5f4', '#6da7ec', '#3987e5',
  '#256abf', '#184f95', '#0d366b',
]

export const TREND = {
  increasing: { color: '#e34948', glyph: '▲', label: 'increasing' },
  decreasing: { color: '#2a78d6', glyph: '▼', label: 'decreasing' },
  'no trend': { color: '#6b6a66', glyph: '▬', label: 'no trend' },
}

// Interpolate the year ramp to a hex for fraction t in [0, 1].
export function yearColor(t) {
  const n = YEAR_RAMP.length - 1
  const clamped = Math.max(0, Math.min(1, t))
  const i = Math.min(n - 1, Math.floor(clamped * n))
  const f = clamped * n - i
  const [r1, g1, b1] = hexToRgb(YEAR_RAMP[i])
  const [r2, g2, b2] = hexToRgb(YEAR_RAMP[i + 1])
  const mix = (a, b) => Math.round(a + (b - a) * f)
  return `rgb(${mix(r1, r2)}, ${mix(g1, g2)}, ${mix(b1, b2)})`
}

function hexToRgb(hex) {
  const h = hex.replace('#', '')
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16))
}
