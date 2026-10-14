import { useEffect, useState, useCallback } from 'react'
import Sidebar from './components/Sidebar'
import Controls from './components/Controls'
import SnowControls from './components/SnowControls'
import BaseflowControls from './components/BaseflowControls'
import BaseflowView from './components/BaseflowView'
import AnalysisView from './components/AnalysisView'
import SnowAnalysisView from './components/SnowAnalysisView'
import { listSites, analyze, listSnotelSites, analyzeSnow, analyzeBaseflow } from './api'

const DEFAULT_PARAMS = {
  start_date: '1930-10-01',
  end_date: new Date().toISOString().slice(0, 10),
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
  start_date: '1995-10-01',
  end_date: '2025-09-30',
  methods: ['lyne_hollick', 'eckhardt', 'local_minimum'],
  eckhardt_bfi_max: 0.8,
  alpha: 0.1,
}

const SOURCE_LABELS = {
  streamflow: 'Streamflow (USGS)',
  snow: 'Snowpack (SNOTEL)',
  baseflow: 'Baseflow (USGS)',
}

const STATES = {
  streamflow: ['', 'WA', 'OR', 'ID'],
  baseflow: ['', 'WA', 'OR', 'ID'],
  snow: ['', 'WA', 'OR', 'ID', 'MT', 'WY'],
}

// Normalise both catalogs to a common display shape for the map/list.
function toDisplay(s, source) {
  return source !== 'snow'
    ? { id: s.site_no, name: s.name, state: s.state, lat: s.lat, long: s.long }
    : { id: s.station_triplet, name: s.name, state: s.state, lat: s.lat, long: s.long }
}

export default function App() {
  const [source, setSource] = useState('streamflow')
  const [allSites, setAllSites] = useState([])
  const [sitesLoading, setSitesLoading] = useState(true)
  const [query, setQuery] = useState('')
  const [state, setState] = useState('')

  const [selected, setSelected] = useState(null)
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [snowParams, setSnowParams] = useState(DEFAULT_SNOW_PARAMS)
  const [baseflowParams, setBaseflowParams] = useState(DEFAULT_BASEFLOW_PARAMS)
  const [result, setResult] = useState(null)
  const [resultSource, setResultSource] = useState(null) // which source `result` belongs to
  const [running, setRunning] = useState(false)
  const [error, setError] = useState(null)

  // (Re)load the catalog whenever the data source changes.
  useEffect(() => {
    setSitesLoading(true)
    setSelected(null)
    setResult(null)
    setError(null)
    setQuery('')
    setState('')
    const loader = source !== 'snow' ? listSites : listSnotelSites
    loader({})
      .then((list) => setAllSites(list.map((s) => toDisplay(s, source))))
      .catch((e) => setError(e.message))
      .finally(() => setSitesLoading(false))
  }, [source])

  const filtered = allSites.filter(
    (s) =>
      (!state || s.state === state) &&
      (!query || s.name.toLowerCase().includes(query.toLowerCase())),
  )

  const run = useCallback(
    async (site) => {
      if (!site) return
      setRunning(true)
      setError(null)
      try {
        const res =
          source === 'streamflow'
            ? await analyze({ site_no: site.id, ...params })
            : source === 'baseflow'
              ? await analyzeBaseflow({ site_no: site.id, ...baseflowParams })
              : await analyzeSnow({ station_triplet: site.id, ...snowParams })
        setResult(res)
        setResultSource(source)
      } catch (e) {
        setError(e.message)
        setResult(null)
      } finally {
        setRunning(false)
      }
    },
    [source, params, snowParams, baseflowParams],
  )

  const onSelect = (site) => {
    setSelected(site)
    run(site)
  }

  return (
    <div className="app">
      <header className="app__bar">
        <h1>PNW Streamflow Climate Explorer</h1>
        <div className="source-toggle">
          {['streamflow', 'snow', 'baseflow'].map((src) => (
            <button
              key={src}
              className={`source-tab ${source === src ? 'source-tab--active' : ''}`}
              onClick={() => {
                if (src === source) return
                // Clear prior-source result synchronously so no stale-shaped
                // result is handed to the wrong analysis view during re-render.
                setSelected(null)
                setResult(null)
                setResultSource(null)
                setSource(src)
              }}
            >
              {SOURCE_LABELS[src]}
            </button>
          ))}
        </div>
        <span className="app__tag">Mann-Kendall trend detection</span>
      </header>

      <div className="app__body">
        <Sidebar
          sites={filtered}
          loading={sitesLoading}
          query={query}
          setQuery={setQuery}
          state={state}
          setState={setState}
          states={STATES[source]}
          selected={selected}
          onSelect={onSelect}
        />

        <main className="main">
          {selected ? (
            <>
              {source === 'streamflow' ? (
                <Controls params={params} setParams={setParams} onRun={() => run(selected)} running={running} />
              ) : source === 'baseflow' ? (
                <BaseflowControls params={baseflowParams} setParams={setBaseflowParams} onRun={() => run(selected)} running={running} />
              ) : (
                <SnowControls params={snowParams} setParams={setSnowParams} onRun={() => run(selected)} running={running} />
              )}
              {error && <div className="banner banner--error">{error}</div>}
              {running && !result && <div className="placeholder">Fetching data and computing trends…</div>}
              {result && resultSource === 'streamflow' && <AnalysisView result={result} />}
              {result && resultSource === 'baseflow' && <BaseflowView result={result} />}
              {result && resultSource === 'snow' && <SnowAnalysisView result={result} />}
            </>
          ) : (
            <div className="placeholder placeholder--intro">
              <h2>Select a {source === 'snow' ? 'SNOTEL station' : 'streamflow gage'}</h2>
              <p>
                {source === 'baseflow'
                  ? 'Pick a gage to separate its daily record into baseflow (groundwater-fed flow) using three methods and test summer baseflow, baseflow index, and recession for trends. Results are reported as a range across methods.'
                  : source === 'streamflow'
                  ? 'Pick a gage on the map or from the list to fetch its full daily record from USGS and test it for climate-change signals — shifts in runoff timing, seasonal volume, and peak flow.'
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
