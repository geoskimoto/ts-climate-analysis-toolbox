import { useState, useEffect } from 'react'
import { getSnotelCandidates, analyzePaired } from '../api'
import PairedView from './PairedView'

// From an analyzed streamflow gage: fetch candidate SNOTEL stations in its
// basin, let the user pick one (the curation step), and show the paired
// snow<->streamflow comparison over the co-registered window.
export default function PairingPanel({ siteNo }) {
  const [open, setOpen] = useState(false)
  const [candidates, setCandidates] = useState(null)
  const [chosen, setChosen] = useState(null)
  const [paired, setPaired] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  // Reset when the gage changes.
  useEffect(() => {
    setOpen(false)
    setCandidates(null)
    setChosen(null)
    setPaired(null)
    setError(null)
  }, [siteNo])

  const expand = async () => {
    setOpen(true)
    if (candidates) return
    setLoading(true)
    setError(null)
    try {
      setCandidates(await getSnotelCandidates(siteNo))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const choose = async (c) => {
    setChosen(c.station_triplet)
    setPaired(null)
    setLoading(true)
    setError(null)
    try {
      setPaired(await analyzePaired({ site_no: siteNo, station_triplet: c.station_triplet }))
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <section className="pairing">
      <div className="pairing__head">
        <h3>Basin snowpack pairing</h3>
        {!open && (
          <button className="btn btn--ghost" onClick={expand}>Compare with basin snowpack →</button>
        )}
      </div>

      {open && (
        <>
          <p className="pairing__intro">
            SNOTEL stations in this gage's basin (same HUC-8) or nearby, sitting above the gage.
            These are <em>suggestions</em> — pick one you judge to represent the contributing
            snowpack. Prefer a long record for a meaningful shared window.
          </p>

          {loading && !candidates && <div className="placeholder">Finding candidate stations…</div>}
          {error && <div className="banner banner--error">{error}</div>}

          {candidates && candidates.length === 0 && (
            <div className="placeholder">No SNOTEL stations found in this gage's basin.</div>
          )}

          {candidates && candidates.length > 0 && (
            <div className="cand-list">
              {candidates.map((c) => (
                <button
                  key={c.station_triplet}
                  className={`cand ${chosen === c.station_triplet ? 'cand--active' : ''}`}
                  onClick={() => choose(c)}
                >
                  <span className="cand__name">{c.name}</span>
                  <span className="cand__meta">
                    {c.same_huc8 ? <span className="cand__tag cand__tag--huc">same HUC-8</span>
                      : <span className="cand__tag">nearby</span>}
                    {c.distance_miles} mi · +{c.elevation_diff_ft} ft · since {c.begin_date?.slice(0, 4)}
                  </span>
                </button>
              ))}
            </div>
          )}

          {loading && chosen && <div className="placeholder">Computing paired trends over the shared window…</div>}
          {paired && <PairedView paired={paired} />}
        </>
      )}
    </section>
  )
}
