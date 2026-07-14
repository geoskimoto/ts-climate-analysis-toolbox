import { MapContainer, TileLayer, CircleMarker, Tooltip } from 'react-leaflet'
import { SERIES_BLUE } from '../palette'

// Map of all catalog sites; click a marker to select it. The selected site is
// enlarged and recolored so identity follows the entity, not the marker order.
export default function SiteMap({ sites, selected, onSelect }) {
  return (
    <MapContainer center={[46.2, -119.5]} zoom={6} className="site-map" preferCanvas>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {sites.map((s) => {
        const isSel = s.id === selected
        return (
          <CircleMarker
            key={s.id}
            center={[s.lat, s.long]}
            radius={isSel ? 8 : 4}
            pathOptions={{
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
  )
}
