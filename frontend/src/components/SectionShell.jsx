import { useId } from 'react'

// One analysis section: titled, divided from its neighbours, with its own
// loading / error / retry state so a failure here never blanks another section.
export default function SectionShell({ id, title, status, error, onRetry, controls, children }) {
  const headingId = useId()
  return (
    <section id={id} className="section-shell" aria-labelledby={headingId}>
      <div className="section-shell__divider" data-testid="section-divider" />
      <h2 id={headingId} className="section-shell__title">{title}</h2>
      {controls}
      {status === 'loading' && <div className="placeholder">Fetching data and computing trends…</div>}
      {status === 'error' && (
        <div className="banner banner--error" role="alert">
          <span>{error}</span>
          {onRetry && <button type="button" className="btn" onClick={onRetry}>Retry</button>}
        </div>
      )}
      {status === 'ok' && children}
    </section>
  )
}
