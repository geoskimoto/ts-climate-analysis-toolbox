import SiteMap from './SiteMap'

// Left pane: state filter + text search, the site map, and a scrollable list.
export default function Sidebar({ sites, loading, query, setQuery, state, setState, selected, onSelect, states }) {
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
      </div>

      <SiteMap sites={sites} selected={selected?.id} onSelect={onSelect} />

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
            <span className="site-item__meta">{s.id} · {s.state}</span>
          </button>
        ))}
      </div>
    </aside>
  )
}
