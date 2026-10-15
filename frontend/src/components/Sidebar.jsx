import SiteMap from './SiteMap'

const REG_CHIPS = [['regulated', 'Regulated'], ['unregulated', 'Likely unregulated'], ['unknown', 'Unknown']]
const REG_BADGE = { regulated: 'Regulated', likely_regulated: 'Likely regulated', likely_unregulated: 'Likely unregulated' }

// Left pane: state filter + text search, the site map, and a scrollable list.
export default function Sidebar({ sites, loading, query, setQuery, state, setState, selected, onSelect, states, showRegFilter, regFilter, setRegFilter, regCounts, regMarkers }) {
  const STATES = states || ['', 'WA', 'OR', 'ID']
  return (
    <aside className="sidebar">
      <div className="sidebar__controls">
        <input
          className="input"
          type="search"
          placeholder="Search sites by name…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <div className="state-tabs">
          {STATES.map((s) => (
            <button
              key={s || 'all'}
              className={`state-tab ${state === s ? 'state-tab--active' : ''}`}
              onClick={() => setState(s)}
            >
              {s || 'All'}
            </button>
          ))}
        </div>
        {showRegFilter && (
          <div className="reg-filter" role="group" aria-label="Regulation filter">
            <span className="reg-filter__label">Regulation</span>
            {REG_CHIPS.map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`reg-chip ${regFilter[key] ? 'reg-chip--on' : ''}`}
                aria-pressed={regFilter[key]}
                onClick={() => {
                  const next = { ...regFilter, [key]: !regFilter[key] }
                  if (Object.values(next).some(Boolean)) setRegFilter(next) // keep at least one on
                }}
              >
                {label} <span className="reg-chip__n">{regCounts[key]}</span>
              </button>
            ))}
          </div>
        )}
      </div>

      <SiteMap sites={sites} selected={selected?.id} onSelect={onSelect} regMarkers={regMarkers} />

      <div className="site-list">
        <div className="site-list__count">
          {loading ? 'Loading…' : `${sites.length} sites`}
        </div>
        {sites.map((s) => (
          <button
            key={s.id}
            className={`site-item ${selected?.id === s.id ? 'site-item--active' : ''}`}
            onClick={() => onSelect(s)}
          >
            <span className="site-item__name">{s.name}</span>
            <span className="site-item__meta">
              {s.id} · {s.state}
              {REG_BADGE[s.regulation_level] && (
                <span className={`reg-badge reg-badge--${s.regulation_level}`} title={s.regulation_reason || undefined}>
                  {REG_BADGE[s.regulation_level]}
                </span>
              )}
            </span>
          </button>
        ))}
      </div>
    </aside>
  )
}
