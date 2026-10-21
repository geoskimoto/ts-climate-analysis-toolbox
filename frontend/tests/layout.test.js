import { describe, it, expect } from 'vitest'
import {
  SIDEBAR_MIN, SIDEBAR_DEFAULT, sidebarMax, clampSidebarWidth,
  nextWidthForKey, mapHeightForWidth, loadSidebarWidth, saveSidebarWidth,
} from '../src/lib/layout.js'

const mem = (init = {}) => {
  const d = { ...init }
  return { d, getItem: (k) => (k in d ? d[k] : null), setItem: (k, v) => { d[k] = String(v) } }
}
const throwing = { getItem() { throw new Error('denied') }, setItem() { throw new Error('quota') } }

describe('constants and sidebarMax', () => {
  it('has spec constants', () => {
    expect(SIDEBAR_MIN).toBe(280)
    expect(SIDEBAR_DEFAULT).toBe(350)
  })
  it('is 70% of viewport, floored', () => {
    expect(sidebarMax(1000)).toBe(700)
    expect(sidebarMax(1001)).toBe(700)
    expect(sidebarMax(1919)).toBe(1343)
  })
  it('never drops below SIDEBAR_MIN on tiny viewports', () => {
    expect(sidebarMax(300)).toBe(280)
    expect(sidebarMax(0)).toBe(280)
  })
})

describe('clampSidebarWidth', () => {
  it('passes through in-range values', () => expect(clampSidebarWidth(400, 1200)).toBe(400))
  it('clamps below min', () => expect(clampSidebarWidth(100, 1200)).toBe(280))
  it('clamps above max', () => expect(clampSidebarWidth(5000, 1000)).toBe(700))
  it('rounds to integer', () => {
    expect(clampSidebarWidth(400.4, 1200)).toBe(400)
    expect(clampSidebarWidth(400.6, 1200)).toBe(401)
  })
  it('non-finite input falls back to default', () => {
    expect(clampSidebarWidth(NaN, 1200)).toBe(350)
    expect(clampSidebarWidth(undefined, 1200)).toBe(350)
    expect(clampSidebarWidth(Infinity, 1200)).toBe(350)
  })
  it('default fallback is itself clamped on tiny viewports', () => {
    expect(clampSidebarWidth(NaN, 300)).toBe(280)
  })
  it('on tiny viewport everything is min', () => expect(clampSidebarWidth(600, 100)).toBe(280))
})

describe('nextWidthForKey', () => {
  it('ArrowLeft shrinks by 16', () => expect(nextWidthForKey('ArrowLeft', 400, 1200)).toBe(384))
  it('ArrowRight grows by 16', () => expect(nextWidthForKey('ArrowRight', 400, 1200)).toBe(416))
  it('ArrowLeft clamps at min', () => expect(nextWidthForKey('ArrowLeft', 285, 1200)).toBe(280))
  it('ArrowRight clamps at max', () => expect(nextWidthForKey('ArrowRight', 695, 1000)).toBe(700))
  it('Home goes to min', () => expect(nextWidthForKey('Home', 500, 1200)).toBe(280))
  it('End goes to sidebarMax', () => expect(nextWidthForKey('End', 500, 1000)).toBe(700))
  it('other keys return null', () => {
    for (const k of ['a', 'Enter', 'ArrowUp', 'ArrowDown', 'Tab', ' ']) {
      expect(nextWidthForKey(k, 400, 1200)).toBeNull()
    }
  })
})

describe('mapHeightForWidth', () => {
  it('is 240 at default width', () => expect(mapHeightForWidth(350)).toBe(240))
  it('scales proportionally', () => expect(mapHeightForWidth(700)).toBe(480))
  it('clamps at 240 floor', () => expect(mapHeightForWidth(100)).toBe(240))
  it('clamps at 640 ceiling', () => expect(mapHeightForWidth(5000)).toBe(640))
  it('returns an integer', () => expect(Number.isInteger(mapHeightForWidth(433))).toBe(true))
})

describe('load/saveSidebarWidth', () => {
  it('round-trips through storage under key sidebarWidth', () => {
    const s = mem()
    saveSidebarWidth(s, 420)
    expect(s.d.sidebarWidth).toBe('420')
    expect(loadSidebarWidth(s, 1200)).toBe(420)
  })
  it('returns default when missing', () => expect(loadSidebarWidth(mem(), 1200)).toBe(350))
  it('returns default for non-numeric', () => {
    expect(loadSidebarWidth(mem({ sidebarWidth: 'abc' }), 1200)).toBe(350)
    expect(loadSidebarWidth(mem({ sidebarWidth: 'NaN' }), 1200)).toBe(350)
  })
  it('clamps stored value to the current viewport', () => {
    expect(loadSidebarWidth(mem({ sidebarWidth: '900' }), 1000)).toBe(700)
    expect(loadSidebarWidth(mem({ sidebarWidth: '10' }), 1000)).toBe(280)
  })
  it('null/undefined storage gives default', () => {
    expect(loadSidebarWidth(null, 1200)).toBe(350)
    expect(loadSidebarWidth(undefined, 1200)).toBe(350)
  })
  it('throwing storage gives default on load and never throws on save', () => {
    expect(loadSidebarWidth(throwing, 1200)).toBe(350)
    expect(() => saveSidebarWidth(throwing, 400)).not.toThrow()
  })
  it('save tolerates null storage', () => expect(() => saveSidebarWidth(null, 400)).not.toThrow())
})
