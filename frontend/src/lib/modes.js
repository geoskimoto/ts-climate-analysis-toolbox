// Top-level analysis modes. Streamflow and baseflow share the USGS catalog.
export const MODES = ['hydro', 'snow']
export const MODE_LABELS = { hydro: 'Streamflow & Baseflow', snow: 'Snowpack (SNOTEL)' }

const CATALOGS = { hydro: 'usgs', snow: 'snotel' }

export function catalogFor(mode) {
  if (!(mode in CATALOGS)) throw new Error(`Unknown mode: ${mode}`)
  return CATALOGS[mode]
}

export const keepSelectionOnModeChange = (from, to) => catalogFor(from) === catalogFor(to)
