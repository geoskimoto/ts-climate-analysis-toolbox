import { TREND } from '../palette'

// A single Mann-Kendall verdict: direction (arrow + color), significance, and
// the numeric slope/p. The arrow means the trend direction is never color-only.
export default function MannKendallCard({ title, mk, unit, help }) {
  const t = TREND[mk.trend] || TREND['no trend']
  return (
    <div className="mk-card">
      <div className="mk-card__title" title={help}>{title}</div>
      <div className="mk-card__verdict" style={{ color: t.color }}>
        <span className="mk-card__glyph">{t.glyph}</span>
        <span className="mk-card__trend">{t.label}</span>
      </div>
      <div className="mk-card__stats">
        <span className={`mk-badge ${mk.significant ? 'mk-badge--sig' : 'mk-badge--ns'}`}>
          {mk.significant ? 'significant' : 'not significant'}
        </span>
        <span className="mk-card__p">p = {mk.p_value.toFixed(3)}</span>
      </div>
      <div className="mk-card__slope">
        {mk.slope >= 0 ? '+' : ''}{formatSlope(mk.slope)} {unit}
      </div>
    </div>
  )
}

function formatSlope(s) {
  const abs = Math.abs(s)
  if (abs !== 0 && abs < 0.001) return s.toExponential(2)
  return s.toFixed(abs < 1 ? 4 : 2)
}
