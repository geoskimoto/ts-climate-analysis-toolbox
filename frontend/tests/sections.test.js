import { describe, it, expect } from 'vitest'
import { SECTIONS, pickActiveSection } from '../src/lib/sections.js'

describe('SECTIONS', () => {
  it('is streamflow then baseflow', () => {
    expect(SECTIONS).toEqual([
      { id: 'streamflow', label: 'Streamflow' },
      { id: 'baseflow', label: 'Baseflow' },
    ])
  })
})

describe('pickActiveSection', () => {
  it('picks first section when none has reached the offset', () => {
    expect(pickActiveSection({ streamflow: 200, baseflow: 900 })).toBe('streamflow')
  })
  it('picks first when all are below the offset line (far below)', () => {
    expect(pickActiveSection({ streamflow: 500, baseflow: 800 }, 80)).toBe('streamflow')
  })
  it('picks the last section whose top <= offset', () => {
    expect(pickActiveSection({ streamflow: -300, baseflow: 40 })).toBe('baseflow')
  })
  it('keeps first active while second is still below', () => {
    expect(pickActiveSection({ streamflow: -300, baseflow: 300 })).toBe('streamflow')
  })
  it('top exactly at offset counts as reached', () => {
    expect(pickActiveSection({ streamflow: -10, baseflow: 80 }, 80)).toBe('baseflow')
    expect(pickActiveSection({ streamflow: -10, baseflow: 81 }, 80)).toBe('streamflow')
  })
  it('respects a custom offset', () => {
    expect(pickActiveSection({ streamflow: 0, baseflow: 150 }, 200)).toBe('baseflow')
  })
  it('ignores missing ids', () => {
    expect(pickActiveSection({ baseflow: 10 })).toBe('baseflow')
    expect(pickActiveSection({ streamflow: -5 })).toBe('streamflow')
    expect(pickActiveSection({})).toBe('streamflow')
  })
  it('uses SECTIONS order, not key order', () => {
    expect(pickActiveSection({ baseflow: -50, streamflow: -100 })).toBe('baseflow')
  })
})
