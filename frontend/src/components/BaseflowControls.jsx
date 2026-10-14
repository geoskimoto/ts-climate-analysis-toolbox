import { useState } from 'react'
import { METHOD_STYLE } from '../palette'

const METHODS = ['lyne_hollick', 'eckhardt', 'local_minimum']

const isFrac = (v) => {
  const n = Number(v)
  return v !== '' && Number.isFinite(n) && n > 0 && n < 1
}

// Parameter controls for baseflow separation. Numeric fields keep their raw
// text locally (so "0." can be typed) and only push valid numbers upward.
export default function BaseflowControls({ params, setParams, onRun, running }) {
  const [bfiText, setBfiText] = useState(String(params.eckhardt_bfi_max))
  const [alphaText, setAlphaText] = useState(String(params.alpha))

  const setDate = (k) => (e) => setParams({ ...params, [k]: e.target.value })
  const setNum = (k, setText) => (e) => {
    setText(e.target.value)
    if (isFrac(e.target.value)) setParams({ ...params, [k]: Number(e.target.value) })
  }
  const toggle = (m) => {
    const on = params.methods.includes(m)
    if (on && params.methods.length === 1) return // keep at least one method
    setParams({
      ...params,
      methods: on ? params.methods.filter((x) => x !== m) : METHODS.filter((x) => x === m || params.methods.includes(x)),
    })
  }

  const bfiOk = isFrac(bfiText)
  const alphaOk = isFrac(alphaText)
  const datesOk = params.start_date && params.end_date && params.start_date < params.end_date
  const valid = bfiOk && alphaOk && datesOk

  return (
    <form
      className="controls"
      onSubmit={(e) => {
        e.preventDefault()
        if (valid) onRun()
      }}
    >
      <label className="field">
        <span>Start</span>
        <input className="input" type="date" value={params.start_date} onChange={setDate('start_date')} />
      </label>
      <label className="field">
        <span>End</span>
        <input className="input" type="date" value={params.end_date} onChange={setDate('end_date')} />
      </label>
      <fieldset className="fieldset-reset">
        <legend className="bf-legend" style={{ fontSize: '11.5px', color: 'var(--ink-3)', padding: 0 }}>Methods (at least one)</legend>
        <div className="field--methods" style={{ display: 'flex', gap: 12, minHeight: 32, alignItems: 'center' }}>
          {METHODS.map((m) => (
            <label key={m} className="field field--check">
              <input
                type="checkbox"
                checked={params.methods.includes(m)}
                disabled={params.methods.includes(m) && params.methods.length === 1}
                onChange={() => toggle(m)}
              />
              <span>{METHOD_STYLE[m].name}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <label className="field field--sm">
        <span>Eckhardt BFImax</span>
        <input className="input" type="number" min="0.01" max="0.99" step="0.01"
          value={bfiText} onChange={setNum('eckhardt_bfi_max', setBfiText)}
          aria-invalid={!bfiOk} style={bfiOk ? undefined : { borderColor: '#a12a2a' }} />
        {!bfiOk && <span style={{ color: '#a12a2a' }}>must be between 0 and 1</span>}
      </label>
      <label className="field field--sm">
        <span>α</span>
        <input className="input" type="number" min="0.01" max="0.99" step="0.01"
          value={alphaText} onChange={setNum('alpha', setAlphaText)}
          aria-invalid={!alphaOk} style={alphaOk ? undefined : { borderColor: '#a12a2a' }} />
        {!alphaOk && <span style={{ color: '#a12a2a' }}>must be between 0 and 1</span>}
      </label>
      <button className="btn" type="submit" disabled={running || !valid}>
        {running ? 'Running…' : 'Run analysis'}
      </button>
    </form>
  )
}
