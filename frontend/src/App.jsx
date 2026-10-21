import { useEffect, useState, useCallback, useRef } from 'react'
import Sidebar from './components/Sidebar'
import Controls from './components/Controls'
import SnowControls from './components/SnowControls'
import BaseflowControls from './components/BaseflowControls'
import BaseflowView from './components/BaseflowView'
import AnalysisView from './components/AnalysisView'
import SnowAnalysisView from './components/SnowAnalysisView'
import SectionNav from './components/SectionNav'
import SectionShell from './components/SectionShell'
import Splitter from './components/Splitter'
import { listSites, analyze, listSnotelSites, analyzeSnow, analyzeBaseflow, getDefaults } from './api'
import { MODES, MODE_LABELS, keepSelectionOnModeChange } from './lib/modes'
import { SECTIONS, pickActiveSection } from './lib/sections'
import { createResultCache } from './lib/resultCache'
import { loadAnalyses } from './lib/loadAnalyses'
import { streamflowRegulationNote } from './lib/regulationNote'
import { clampSidebarWidth, loadSidebarWidth, saveSidebarWidth, mapHeightForWidth } from './lib/layout'

// start_date / end_date are filled from GET /api/defaults (1985-10-01 to the end of
// the last complete water year); blank dates are omitted so the backend applies the same defaults.
const DEFAULT_PARAMS = {
  start_date: '',
  end_date: '',
  threshold_percent: 0.5,
  alpha: 0.1,
  peak_window_size: 7,
  ignore_winter_months: false,
}

const DEFAULT_SNOW_PARAMS = {
  start_date: '1980-10-01',
  end_date: new Date().toISOString().slice(0, 10),
  benchmark_month_day: '04-01',
  alpha: 0.1,
}

const DEFAULT_BASEFLOW_PARAMS = {
  start_date: '',
  end_date: '',
  methods: ['lyne_hollick', 'eckhardt', 'local_minimum'],
  eckhardt_bfi_max: 0.8,
  alpha: 0.1,
}

const STATES = {
  hydro: ['', 'WA', 'OR', 'ID'],
  snow: ['', 'WA', 'OR', 'ID', 'MT', 'WY'],
}

const withoutBlankDates = (p) => Object.fromEntries(Object.entries(p).filter(([k, v]) => !(k.endsWith('_date') && v === '')))
const IDLE = { status: 'idle' }

// Normalise both catalogs to a common display shape for the map/list.
function toDisplay(s, mode) {
  return mode !== 'snow'
    ? {
        id: s.site_no, name: s.name, state: s.state, lat: s.lat, long: s.long,
        regulation_level: s.regulation_level ?? 'unknown',
        regulation_reason: s.regulation_reason ?? null,
        hasRegulation: s.regulation_level != null,
      }
    : { id: s.station_triplet, name: s.name, state: s.state, lat: s.lat, long: s.long }
}

// Filter chip -> the API regulation levels it covers.
const REG_GROUPS = {
  regulated: ['regulated', 'likely_regulated'],
  unregulated: ['likely_unregulated'],
  unknown: ['unknown'],
}
const ALL_REG = { regulated: true, unregulated: true, unknown: true }
const regGroup = (level) => (REG_GROUPS.regulated.includes(level) ? 'regulated' : level === 'likely_unregulated' ? 'unregulated' : 'unknown')

export default function App() {
  const [mode, setMode] = useState('hydro')
  const [allSites, setAllSites] = useState([])
  const [sitesLoading, setSitesLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [state, setState] = useState('')
  const [regFilter, setRegFilter] = useState(ALL_REG)

  const [selected, setSelected] = useState(null)
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [snowParams, setSnowParams] = useState(DEFAULT_SNOW_PARAMS)
  const [baseflowParams, setBaseflowParams] = useState(DEFAULT_BASEFLOW_PARAMS)
  const [analyses, setAnalyses] = useState({ streamflow: IDLE, baseflow: IDLE })
  const [snowResult, setSnowResult] = useState(null)
  const [snowRunning, setSnowRunning] = useState(false)
  const [error, setError] = useState(null)

  const [sidebarWidth, setSidebarWidth] = useState(() => loadSidebarWidth(safeStorage(), window.innerWidth))
  const [viewportWidth, setViewportWidth] = useState(window.innerWidth)
  const [activeSection, setActiveSection] = useState(SECTIONS[0].id)

  const cache = useRef(createResultCache())
  const siteToken = useRef(0) // bumps on every site/mode change so late results from an old site are dropped
  const mainRef = useRef(null)

  // Default analysis window from the backend (single source of truth).
  useEffect(() => {
    getDefaults()
      .then(({ start_date, end_date }) => {
        setParams((p) => ({ ...p, start_date: p.start_date || start_date, end_date: p.end_date || end_date }))
        setBaseflowParams((p) => ({ ...p, start_date: p.start_date || start_date, end_date: p.end_date || end_date }))
      })
      .catch(() => { /* blank dates are omitted; the API applies the same defaults */ })
  }, [])

  // Track viewport + persist the sidebar width.
  useEffect(() => {
    const onResize = () => {
      setViewportWidth(window.innerWidth)
      setSidebarWidth((w) => clampSidebarWidth(w, window.innerWidth))
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])
  useEffect(() => saveSidebarWidth(safeStorage(), sidebarWidth), [sidebarWidth])

  // (Re)load the catalog whenever the catalog (mode) changes.
  useEffect(() => {
    setSitesLoading(true)
    setError(null)
    setQuery('')
    setState('')
    setRegFilter(ALL_REG)
    const loader = mode !== 'snow' ? listSites : listSnotelSites
    loader({})
      .then((list) => setAllSites(list.map((s) => toDisplay(s, mode))))
      .catch((e) => setError(e.message))
      .finally(() => setSitesLoading(false))
  }, [mode])

  const baseFiltered = allSites.filter(
    (s) =>
      (!state || s.state === state) &&
      (!query || s.name.toLowerCase().includes(query.toLowerCase())),
  )
  // Regulation filter: streamflow/baseflow only, and only if the API supplies it.
  const showRegFilter = mode !== 'snow' && allSites.length > 0 && allSites.every((s) => s.hasRegulation)
  const regCounts = { regulated: 0, unregulated: 0, unknown: 0 }
  baseFiltered.forEach((s) => { regCounts[regGroup(s.regulation_level)] += 1 })
  const filtered = showRegFilter ? baseFiltered.filter((s) => regFilter[regGroup(s.regulation_level)]) : baseFiltered

  // Run the given analyses (cached ones return instantly) for a site. Each
  // section updates as soon as its own request settles; a failure stays local.
  const runHydro = useCallback(
    (site, kinds = ['streamflow', 'baseflow'], { force = false } = {}) => {
      if (!site) return
      const token = siteToken.current
      const specs = kinds.map((kind) => ({
        kind,
        params: kind === 'streamflow' ? params : baseflowParams,
        run: (p) => (kind === 'streamflow'
          ? analyze({ site_no: site.id, ...withoutBlankDates(p) })
          : analyzeBaseflow({ site_no: site.id, ...withoutBlankDates(p) })),
      }))
      if (force) specs.forEach((sp) => cache.current.set(sp.kind, site.id, sp.params, undefined))
      loadAnalyses({
        siteId: site.id,
        specs,
        cache: cache.current,
        onUpdate: (kind, st) => {
          if (token === siteToken.current) setAnalyses((a) => ({ ...a, [kind]: st }))
        },
      }).then((out) => {
        // Cached results settle without onUpdate, so apply the final states here.
        if (token === siteToken.current) setAnalyses((a) => ({ ...a, ...out }))
      })
    },
    [params, baseflowParams],
  )

  const runSnow = useCallback(
    async (site) => {
      if (!site) return
      const token = siteToken.current
      setSnowRunning(true)
      setError(null)
      try {
        const res = await analyzeSnow({ station_triplet: site.id, ...snowParams })
        if (token === siteToken.current) setSnowResult(res)
      } catch (e) {
        if (token === siteToken.current) { setError(e.message); setSnowResult(null) }
      } finally {
        if (token === siteToken.current) setSnowRunning(false)
      }
    },
    [snowParams],
  )

  const onSelect = (site) => {
    siteToken.current += 1
    setSelected(site)
    setSnowResult(null)
    setError(null)
    setAnalyses({ streamflow: IDLE, baseflow: IDLE })
    if (mode === 'snow') runSnow(site)
    else runHydro(site)
  }

  const switchMode = (next) => {
    if (next === mode) return
    if (!keepSelectionOnModeChange(mode, next)) {
      // Different catalog: the old selection and results mean nothing here.
      siteToken.current += 1
      setSelected(null)
      setSnowResult(null)
      setAnalyses({ streamflow: IDLE, baseflow: IDLE })
    }
    setMode(next)
  }

  // Sticky-nav highlight follows the scroll position.
  useEffect(() => {
    const main = mainRef.current
    if (!main || mode === 'snow' || !selected) return undefined
    let raf = 0
    const update = () => {
      raf = 0
      const top = main.getBoundingClientRect().top
      const tops = {}
      SECTIONS.forEach(({ id }) => {
        const el = document.getElementById(id)
        if (el) tops[id] = el.getBoundingClientRect().top - top
      })
      setActiveSection(pickActiveSection(tops))
    }
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update) }
    main.addEventListener('scroll', onScroll, { passive: true })
    return () => { main.removeEventListener('scroll', onScroll); if (raf) cancelAnimationFrame(raf) }
  }, [mode, selected])

  const goToSection = (id) => {
    setActiveSection(id)
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const regNote = streamflowRegulationNote(selected?.regulation_level)
  const sf = analyses.streamflow
  const bf = analyses.baseflow

  return (
    <div className="app">
      <header className="app__bar">
        <h1>PNW Streamflow Climate Explorer</h1>
        <div className="source-toggle">
          {MODES.map((m) => (
            <button
              key={m}
              className={`source-tab ${mode === m ? 'source-tab--active' : ''}`}
              onClick={() => switchMode(m)}
            >
              {MODE_LABELS[m]}
            </button>
          ))}
        </div>
        <span className="app__tag">Mann-Kendall trend detection</span>
      </header>

      <div
        className="app__body"
        style={{ '--sidebar-width': `${sidebarWidth}px`, '--map-height': `${mapHeightForWidth(sidebarWidth)}px` }}
      >
        <Sidebar
          sites={filtered}
          loading={sitesLoading}
          query={query}
          setQuery={setQuery}
          state={state}
          setState={setState}
          states={STATES[mode]}
          showRegFilter={showRegFilter}
          regFilter={regFilter}
          setRegFilter={setRegFilter}
          regCounts={regCounts}
          regMarkers={mode !== 'snow'}
          selected={selected}
          onSelect={onSelect}
        />
        <Splitter width={sidebarWidth} onChange={setSidebarWidth} viewportWidth={viewportWidth} />

        <main className="main" ref={mainRef}>
          {selected && mode === 'snow' && (
            <>
              <SnowControls params={snowParams} setParams={setSnowParams} onRun={() => runSnow(selected)} running={snowRunning} />
              {error && <div className="banner banner--error">{error}</div>}
              {snowRunning && !snowResult && <div className="placeholder">Fetching data and computing trends…</div>}
              {snowResult && <SnowAnalysisView result={snowResult} />}
            </>
          )}

          {selected && mode === 'hydro' && (
            <div className="analysis-page">
              <header className="analysis__header analysis-page__head">
                <h2>{selected.name}</h2>
                <div className="analysis__submeta">
                  <span>USGS {selected.id}</span>
                  <span>{selected.state}</span>
                  {selected.regulation_level && selected.regulation_level !== 'unknown' && (
                    <span className={`reg-badge reg-badge--${selected.regulation_level}`} title={selected.regulation_reason || undefined}>
                      {selected.regulation_level.replace(/_/g, ' ')}
                    </span>
                  )}
                </div>
              </header>
              <SectionNav sections={SECTIONS} active={activeSection} onNavigate={goToSection} />

              <SectionShell
                id="streamflow"
                title="Streamflow"
                status={sf.status}
                error={sf.error}
                onRetry={() => runHydro(selected, ['streamflow'], { force: true })}
                controls={
                  <>
                    <Controls params={params} setParams={setParams} onRun={() => runHydro(selected, ['streamflow'], { force: true })} running={sf.status === 'loading'} />
                    {regNote && <p className="hydro-reg-note" role="note">{regNote}</p>}
                  </>
                }
              >
                {sf.data && <AnalysisView result={sf.data} hideHeader />}
              </SectionShell>

              <SectionShell
                id="baseflow"
                title="Baseflow"
                status={bf.status}
                error={bf.error}
                onRetry={() => runHydro(selected, ['baseflow'], { force: true })}
                controls={<BaseflowControls params={baseflowParams} setParams={setBaseflowParams} onRun={() => runHydro(selected, ['baseflow'], { force: true })} running={bf.status === 'loading'} />}
              >
                {bf.data && <BaseflowView result={bf.data} hideHeader />}
              </SectionShell>
            </div>
          )}

          {!selected && (
            <div className="placeholder placeholder--intro">
              <h2>Select a {mode === 'snow' ? 'SNOTEL station' : 'streamflow gage'}</h2>
              <p>
                {mode === 'hydro'
                  ? 'Pick a gage on the map or from the list to fetch its daily record from USGS. You get two analyses on one page: streamflow trends (runoff timing, seasonal volume, peak flow) and baseflow (groundwater-fed flow separated three ways, with trends in summer baseflow, baseflow index and recession). Use the section links to jump between them.'
                  : 'Pick a SNOTEL station to fetch its snow water equivalent record from NRCS and test it for snowpack decline — peak SWE, April-1 SWE, and melt-out timing.'}
              </p>
              {error && <div className="banner banner--error">{error}</div>}
            </div>
          )}
        </main>
      </div>
    </div>
  )
}

// localStorage can throw (private mode, blocked site data); the layout helpers tolerate null.
function safeStorage() {
  try { return window.localStorage } catch { return null }
}
