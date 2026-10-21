import { useEffect } from 'react'
import { MapContainer, TileLayer, CircleMarker, Tooltip, useMap } from 'react-leaflet'
import { SERIES_BLUE, REG_VERMILION, REG_GREY } from '../palette'

// Regulation encoded by fill + ring, not colour alone.
function regStyle(level, isSel) {
  if (isSel) return { color: '#0b0b0b', weight: 2, fillColor: '#e34948', fillOpacity: 0.95 }
  if (level === 'regulated' || level === 'likely_regulated')
    return { color: '#0b0b0b', weight: 3, fillColor: REG_VERMILION, fillOpacity: 0.9 }
  if (level === 'likely_unregulated')
    return { color: SERIES_BLUE, weight: 1, fillColor: SERIES_BLUE, fillOpacity: 0.55 }
  return { color: REG_GREY, weight: 2, fillColor: REG_GREY, fillOpacity: 0 }
}

// Leaflet caches its size; tell it whenever the container is resized (splitter drag).
function ResizeSync() {
  const map = useMap()
  useEffect(() => {
    const el = map.getContainer()
    const ro = new ResizeObserver(() => map.invalidateSize())
    ro.observe(el)
    return () => ro.disconnect()
  }, [map])
  return null
}

// Map of all catalog sites; click a marker to select it. The selected site is
// enlarged and recolored so identity follows the entity, not the marker order.
export default function SiteMap({ sites, selected, onSelect, regMarkers }) {
  return (
    <>
    <MapContainer center={[46.2, -119.5]} zoom={6} className="site-map" preferCanvas>
      <ResizeSync />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        // Send the origin as Referer even under a strict document policy
        // (nginx sends same-origin); OSM's tile policy rejects tiles without one.
        referrerPolicy="origin"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {sites.map((s) => {
        const isSel = s.id === selected
        return (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.long]}
            radius={isSel ? 8 : 4}
            pathOptions={regMarkers ? regStyle(s.regulation_level, isSel) : {
              color: isSel ? '#0b0b0b' : SERIES_BLUE,
              weight: isSel ? 2 : 1,
              fillColor: isSel ? '#e34948' : SERIES_BLUE,
              fillOpacity: isSel ? 0.95 : 0.55,
            }}
            eventHandlers={{ click: () => onSelect(s) }}
          >
            <Tooltip>{s.name} ({s.id})</Tooltip>
          </CircleMarker>
        )
      })}
    </MapContainer>
    {regMarkers && (
      <div className="map-legend" aria-label="Map legend">
        <span><i className="map-legend__dot map-legend__dot--reg" /> Regulated</span>
        <span><i className="map-legend__dot map-legend__dot--unreg" /> Likely unregulated</span>
        <span><i className="map-legend__dot map-legend__dot--unk" /> Unknown</span>
      </div>
    )}
    </>
  )
}
