import { describe, it, expect } from 'vitest'
import { MODES, MODE_LABELS, catalogFor, keepSelectionOnModeChange } from '../src/lib/modes.js'

describe('modes', () => {
  it('lists hydro and snow', () => expect(MODES).toEqual(['hydro', 'snow']))
  it('has user-facing labels', () => {
    expect(MODE_LABELS).toEqual({ hydro: 'Streamflow & Baseflow', snow: 'Snowpack (SNOTEL)' })
  })
  it('maps hydro to usgs and snow to snotel', () => {
    expect(catalogFor('hydro')).toBe('usgs')
    expect(catalogFor('snow')).toBe('snotel')
  })
  it('throws on unknown mode', () => {
    expect(() => catalogFor('paired')).toThrow()
    expect(() => catalogFor(undefined)).toThrow()
  })
  it('keeps selection only when catalog is unchanged', () => {
    expect(keepSelectionOnModeChange('hydro', 'hydro')).toBe(true)
    expect(keepSelectionOnModeChange('snow', 'snow')).toBe(true)
    expect(keepSelectionOnModeChange('hydro', 'snow')).toBe(false)
    expect(keepSelectionOnModeChange('snow', 'hydro')).toBe(false)
  })
})
