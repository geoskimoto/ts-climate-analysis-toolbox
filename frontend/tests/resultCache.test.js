import { describe, it, expect } from 'vitest'
import { createResultCache } from '../src/lib/resultCache.js'

describe('resultCache', () => {
  it('returns undefined on miss', () => {
    expect(createResultCache().get('streamflow', '1', { a: 1 })).toBeUndefined()
  })
  it('returns the stored value on hit', () => {
    const c = createResultCache()
    const v = { x: 1 }
    c.set('streamflow', '1', { a: 1 }, v)
    expect(c.get('streamflow', '1', { a: 1 })).toBe(v)
  })
  it('is insensitive to param key order', () => {
    const c = createResultCache()
    c.set('k', 's', { a: 1, b: 2 }, 'v')
    expect(c.get('k', 's', { b: 2, a: 1 })).toBe('v')
  })
  it('is insensitive to key order in nested params', () => {
    const c = createResultCache()
    c.set('k', 's', { o: { x: 1, y: [1, 2] }, a: 1 }, 'v')
    expect(c.get('k', 's', { a: 1, o: { y: [1, 2], x: 1 } })).toBe('v')
  })
  it('misses when a value differs', () => {
    const c = createResultCache()
    c.set('k', 's', { a: 1, b: 2 }, 'v')
    expect(c.get('k', 's', { a: 1, b: 3 })).toBeUndefined()
  })
  it('misses when nested value differs', () => {
    const c = createResultCache()
    c.set('k', 's', { o: { x: 1 } }, 'v')
    expect(c.get('k', 's', { o: { x: 2 } })).toBeUndefined()
  })
  it('isolates kinds and sites', () => {
    const c = createResultCache()
    c.set('streamflow', '1', {}, 'sf1')
    c.set('baseflow', '1', {}, 'bf1')
    c.set('streamflow', '2', {}, 'sf2')
    expect(c.get('streamflow', '1', {})).toBe('sf1')
    expect(c.get('baseflow', '1', {})).toBe('bf1')
    expect(c.get('streamflow', '2', {})).toBe('sf2')
    expect(c.get('baseflow', '2', {})).toBeUndefined()
  })
  it('overwrites on repeated set', () => {
    const c = createResultCache()
    c.set('k', 's', { a: 1 }, 'old')
    c.set('k', 's', { a: 1 }, 'new')
    expect(c.get('k', 's', { a: 1 })).toBe('new')
  })
  it('clear removes everything', () => {
    const c = createResultCache()
    c.set('k', 's', {}, 1)
    c.set('k', 't', {}, 2)
    c.clear()
    expect(c.get('k', 's', {})).toBeUndefined()
    expect(c.get('k', 't', {})).toBeUndefined()
  })
  it('clearSite removes only that site across kinds and params', () => {
    const c = createResultCache()
    c.set('a', 's', { p: 1 }, 1)
    c.set('b', 's', { p: 2 }, 2)
    c.set('a', 't', { p: 1 }, 3)
    c.clearSite('s')
    expect(c.get('a', 's', { p: 1 })).toBeUndefined()
    expect(c.get('b', 's', { p: 2 })).toBeUndefined()
    expect(c.get('a', 't', { p: 1 })).toBe(3)
  })
  it('does not confuse site ids that share a prefix', () => {
    const c = createResultCache()
    c.set('a', '123', {}, 1)
    c.set('a', '1234', {}, 2)
    c.clearSite('123')
    expect(c.get('a', '1234', {})).toBe(2)
  })
  it('caches falsy values distinctly from a miss', () => {
    const c = createResultCache()
    c.set('k', 's', {}, null)
    expect(c.get('k', 's', {})).toBeNull()
  })
})
