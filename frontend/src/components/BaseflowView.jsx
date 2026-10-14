import { useMemo, useState } from 'react'
import MannKendallCard from './MannKendallCard'
import BaseflowTrendChart from './BaseflowTrendChart'
import BaseflowHydrograph from './BaseflowHydrograph'
import { TREND, methodStyle } from '../palette'

const DEFAULT_METRIC = 'augsep_baseflow_cfs'

const fmt = (n) => (n == null ? 'n/a' : Math.abs(n) >= 100 ? Math.round(n).toLocaleString() : Number(n.toPrecision(3)).toString())

// Right pane for the Baseflow mode.
export default function BaseflowView({ result }) {
  const { meta, metric_info, methods, method_range, skipped_methods, example } = result
  const info = Object.fromEntries(metric_info.map((m) => [m.key, m]))
  const [metric, setMetric] = useState(info[DEFAULT_METRIC] ? DEFAULT_METRIC : metric_info[0]?.key)
  const mi = info[metric] || { label: metric, unit: '', description: '' }
  const level = meta.regulation.level
  const reg = {
    regulated: { cls: 'bf-reg--strong', glyph: '⛔', label: 'Flow is regulated' },
    likely_regulated: { cls: 'bf-reg--warn', glyph: '⚠', label: 'Likely regulated' },
    likely_unregulated: { cls: '', glyph: 'ⓘ', label: 'No regulation indicated' },
    unknown: { cls: '', glyph: 'ⓘ', label: 'Regulation unknown' },
  }[level] || { cls: '', glyph: 'ⓘ', label: level }
  const methodsMemo = useMemo(() => methods, [methods])

  return (
    <div className="analysis">
      <header className="analysis__header">
        <h2>{meta.site.name}</h2>
        <div className="analysis__submeta">
          <span>USGS {meta.site.site_no}</span>
          {meta.site.drainage_area_sqmi != null && <span>{Math.round(meta.site.drainage_area_sqmi).toLocaleString()} sq mi</span>}
          <span>Window {meta.window_start} – {meta.window_end}</span>
          <span>{meta.water_years.length} water years</span>
          <span>Eckhardt BFImax {meta.eckhardt_bfi_max}</span>
        </div>
      </header>

      <div className="bf-caveats" role="note">
        <strong>Read with care</strong>
        <ul>{meta.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul>
      </div>
      <div className={`bf-reg ${reg.cls}`} role={level === 'regulated' ? 'alert' : undefined}>
        <span aria-hidden="true">{reg.glyph}</span>
        <span>{reg.label}</span>
        {meta.regulation.reason && <span className="bf-reg__reason">— {meta.regulation.reason}</span>}
        {level === 'regulated' && (
          <span className="bf-reg__reason bf-reg__sentence">Trends here mostly reflect reservoir/diversion operations, not climate.</span>
        )}
      </div>

      <section className="bf-section">
        <h3>Range across methods</h3>
        <table className="bf-table">
          <thead>
            <tr>
              <th>Metric</th><th>Min</th><th>Median</th><th>Max</th>
              <th>Significant decrease</th><th>Significant increase</th>
            </tr>
          </thead>
          <tbody>
            {method_range.map((r) => {
              const i = info[r.metric] || { label: r.metric, unit: '' }
              return (
                <tr key={r.metric}>
                  <td>{i.label}{i.unit ? ` (${i.unit})` : ''}</td>
                  <td>{fmt(r.min)}</td><td>{fmt(r.median)}</td><td>{fmt(r.max)}</td>
                  <td>{TREND.decreasing.glyph} {r.n_sig_decreasing} of {r.n_methods}</td>
                  <td>{TREND.increasing.glyph} {r.n_sig_increasing} of {r.n_methods}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
        <p className="bf-table__note">Report a range, not a single value.</p>
      </section>

      <div className="chart__select-row">
        <label>Metric&nbsp;
          <select className="input input--select" value={metric} onChange={(e) => setMetric(e.target.value)}>
            {metric_info.map((m) => <option key={m.key} value={m.key}>{m.label} ({m.unit})</option>)}
          </select>
        </label>
        {mi.description && <span className="analysis__note" style={{ marginLeft: 10 }}>{mi.description}</span>}
      </div>

      <BaseflowTrendChart
        title={`${mi.label} by water year — one series per method; solid slope line = significant, dashed = not significant`}
        methods={methodsMemo} metricKey={metric} yLabel={mi.label} unit={mi.unit} />

      <section className="bf-cards">
        {methods.map((m) => <MethodCard key={m.method} m={m} metric={metric} info={mi} alpha={meta.alpha} />)}
      </section>

      {example && example.dates?.length > 0 && <BaseflowHydrograph example={example} methods={methods} />}

      <section className="bf-section">
        <h3>Data quality notes</h3>
        <div className="bf-quality">
          {methods.map((m) => <QualityItem key={m.method} m={m} />)}
          {skipped_methods.length > 0 && (
            <div className="bf-quality__item">
              <strong>Skipped methods</strong>
              <ul>{skipped_methods.map((s) => <li key={s.method}>{s.method}: {s.reason}</li>)}</ul>
            </div>
          )}
        </div>
      </section>
    </div>
  )
}

function MethodCard({ m, metric, info, alpha }) {
  const st = methodStyle(m.method)
  const t = m.trends?.[metric]
  if (!t) {
    return (
      <div className="mk-card">
        <div className="bf-method-card__head" style={{ color: st.color }}>{m.label}</div>
        <div className="mk-card__p">Trend not available for this metric (too few valid years).</div>
      </div>
    )
  }
  const o = t.original
  const hr = t.hamed_rao
  const hrT = TREND[hr.trend] || TREND['no trend']
  const mk = { ...o, slope: o.slope ?? 0, p_value: o.p_value ?? NaN }
  return (
    <div>
      <MannKendallCardSafe title={`${m.label} — ${info.label}`} mk={mk} unit={`${info.unit}/yr`} help={info.description} />
      <div className="bf-method-card__extra">
        Hamed-Rao: {hrT.glyph} {hrT.label}, {hr.p_value == null ? 'significance n/a' : `${hr.significant ? 'significant' : 'not significant'} (p = ${hr.p_value.toFixed(3)})`}
        <br />
        Change: {t.slope_pct_per_decade == null ? 'n/a' : `${t.slope_pct_per_decade >= 0 ? '+' : ''}${t.slope_pct_per_decade.toFixed(1)}% per decade`} (α = {alpha})
      </div>
    </div>
  )
}

// MannKendallCard calls p_value.toFixed; shield against null/NaN p-values.
function MannKendallCardSafe({ mk, ...rest }) {
  if (Number.isFinite(mk.p_value)) return <MannKendallCard mk={mk} {...rest} />
  const proxy = { ...mk, p_value: { toFixed: () => 'n/a' } }
  return <MannKendallCard mk={proxy} {...rest} />
}

function QualityItem({ m }) {
  const q = m.quality
  return (
    <div className="bf-quality__item">
      <strong style={{ color: methodStyle(m.method).color }}>{m.label}</strong>
      <div>Interpolated days: {q.n_interpolated}</div>
      <div>Skipped runs: {q.skipped_runs.length === 0 ? 'none' : q.skipped_runs.map((r) => `${r.start} to ${r.end}`).join('; ')}</div>
      {q.excluded_water_years.length === 0 ? <div>Excluded water years: none</div> : (
        <>
          <div>Excluded water years:</div>
          <ul>{q.excluded_water_years.map((e) => <li key={e.water_year}>WY {e.water_year}: {e.reason}</li>)}</ul>
        </>
      )}
    </div>
  )
}
