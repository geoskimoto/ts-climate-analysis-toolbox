import { describe, it, expect, vi } from 'vitest'
import { loadAnalyses } from '../src/lib/loadAnalyses.js'
import { createResultCache } from '../src/lib/resultCache.js'

function deferred() {
  let resolve, reject
  const promise = new Promise((res, rej) => { resolve = res; reject = rej })
  return { promise, resolve, reject }
}
const tick = () => new Promise((r) => setTimeout(r, 0)) // macrotask flush only, not a wait

describe('loadAnalyses', () => {
  it('runs every miss, caches data, and reports ok/fromCache:false', async () => {
    const cache = createResultCache()
    const specs = [
      { kind: 'streamflow', params: { a: 1 }, run: vi.fn().mockResolvedValue({ q: 1 }) },
      { kind: 'baseflow', params: { b: 2 }, run: vi.fn().mockResolvedValue({ bf: 2 }) },
    ]
    const out = await loadAnalyses({ siteId: 's', specs, cache })
    expect(out.streamflow).toEqual({ status: 'ok', data: { q: 1 }, fromCache: false })
    expect(out.baseflow).toEqual({ status: 'ok', data: { bf: 2 }, fromCache: false })
    expect(specs[0].run).toHaveBeenCalledWith({ a: 1 })
    expect(cache.get('streamflow', 's', { a: 1 })).toEqual({ q: 1 })
    expect(cache.get('baseflow', 's', { b: 2 })).toEqual({ bf: 2 })
  })

  it('cache hit skips run and reports fromCache:true', async () => {
    const cache = createResultCache()
    cache.set('streamflow', 's', { a: 1 }, { q: 9 })
    const run = vi.fn()
    const out = await loadAnalyses({ siteId: 's', cache, specs: [{ kind: 'streamflow', params: { a: 1 }, run }] })
    expect(run).not.toHaveBeenCalled()
    expect(out.streamflow).toEqual({ status: 'ok', data: { q: 9 }, fromCache: true })
  })

  it('cache hit works regardless of param key order', async () => {
    const cache = createResultCache()
    cache.set('k', 's', { a: 1, b: 2 }, 'v')
    const run = vi.fn()
    const out = await loadAnalyses({ siteId: 's', cache, specs: [{ kind: 'k', params: { b: 2, a: 1 }, run }] })
    expect(run).not.toHaveBeenCalled()
    expect(out.k.data).toBe('v')
  })

  it('cache miss when params change calls run again', async () => {
    const cache = createResultCache()
    cache.set('k', 's', { a: 1 }, 'old')
    const run = vi.fn().mockResolvedValue('new')
    const out = await loadAnalyses({ siteId: 's', cache, specs: [{ kind: 'k', params: { a: 2 }, run }] })
    expect(run).toHaveBeenCalledTimes(1)
    expect(out.k).toEqual({ status: 'ok', data: 'new', fromCache: false })
  })

  it('mixed hit and miss', async () => {
    const cache = createResultCache()
    cache.set('streamflow', 's', {}, 'cached')
    const run = vi.fn().mockResolvedValue('fresh')
    const out = await loadAnalyses({
      siteId: 's', cache,
      specs: [
        { kind: 'streamflow', params: {}, run: vi.fn() },
        { kind: 'baseflow', params: {}, run },
      ],
    })
    expect(out.streamflow).toMatchObject({ status: 'ok', fromCache: true })
    expect(out.baseflow).toMatchObject({ status: 'ok', fromCache: false })
    expect(run).toHaveBeenCalledTimes(1)
  })

  it('rejection becomes error state with message string and is not cached', async () => {
    const cache = createResultCache()
    const out = await loadAnalyses({
      siteId: 's', cache,
      specs: [{ kind: 'k', params: {}, run: () => Promise.reject(new Error('boom')) }],
    })
    expect(out.k).toEqual({ status: 'error', error: 'boom' })
    expect(cache.get('k', 's', {})).toBeUndefined()
  })

  it('one failure does not affect the other kind, and the promise never rejects', async () => {
    const cache = createResultCache()
    const out = await loadAnalyses({
      siteId: 's', cache,
      specs: [
        { kind: 'streamflow', params: {}, run: () => Promise.reject(new Error('sf down')) },
        { kind: 'baseflow', params: {}, run: () => Promise.resolve('bf') },
      ],
    })
    expect(out.streamflow).toEqual({ status: 'error', error: 'sf down' })
    expect(out.baseflow).toEqual({ status: 'ok', data: 'bf', fromCache: false })
    expect(cache.get('baseflow', 's', {})).toBe('bf')
  })

  it('starts all misses in parallel before any settles', async () => {
    const d1 = deferred(), d2 = deferred()
    const r1 = vi.fn(() => d1.promise), r2 = vi.fn(() => d2.promise)
    const p = loadAnalyses({
      siteId: 's', cache: createResultCache(),
      specs: [{ kind: 'a', params: {}, run: r1 }, { kind: 'b', params: {}, run: r2 }],
    })
    await tick()
    expect(r1).toHaveBeenCalledTimes(1)
    expect(r2).toHaveBeenCalledTimes(1)
    d1.resolve(1); d2.resolve(2)
    await p
  })

  it('onUpdate: loading for each non-cached spec before run, none for cached', async () => {
    const cache = createResultCache()
    cache.set('hit', 's', {}, 'h')
    const events = []
    const onUpdate = (kind, state) => events.push(['u', kind, state.status])
    const run = vi.fn(() => { events.push(['run', 'miss']); return Promise.resolve(1) })
    await loadAnalyses({
      siteId: 's', cache, onUpdate,
      specs: [{ kind: 'hit', params: {}, run: vi.fn() }, { kind: 'miss', params: {}, run }],
    })
    const flat = events.map((e) => e.join(':'))
    expect(flat.indexOf('u:miss:loading')).toBeGreaterThanOrEqual(0)
    expect(flat.indexOf('u:miss:loading')).toBeLessThan(flat.indexOf('run:miss'))
    expect(flat.indexOf('run:miss')).toBeLessThan(flat.indexOf('u:miss:ok'))
    expect(flat.filter((e) => e.startsWith('u:hit:loading'))).toHaveLength(0)
  })

  it('onUpdate: fast spec final update arrives before slow spec settles', async () => {
    const fast = deferred(), slow = deferred()
    const seen = []
    const p = loadAnalyses({
      siteId: 's', cache: createResultCache(),
      onUpdate: (kind, state) => seen.push(`${kind}:${state.status}`),
      specs: [
        { kind: 'slow', params: {}, run: () => slow.promise },
        { kind: 'fast', params: {}, run: () => fast.promise },
      ],
    })
    fast.resolve('F')
    await tick()
    expect(seen).toContain('fast:ok')
    expect(seen).not.toContain('slow:ok')
    expect(seen).toContain('slow:loading')
    slow.resolve('S')
    const out = await p
    expect(seen).toContain('slow:ok')
    expect(out.slow.data).toBe('S')
  })

  it('onUpdate: fast failure is reported before slow success', async () => {
    const fast = deferred(), slow = deferred()
    const seen = []
    const p = loadAnalyses({
      siteId: 's', cache: createResultCache(),
      onUpdate: (kind, state) => seen.push(`${kind}:${state.status}`),
      specs: [
        { kind: 'slow', params: {}, run: () => slow.promise },
        { kind: 'fast', params: {}, run: () => fast.promise },
      ],
    })
    fast.reject(new Error('nope'))
    await tick()
    expect(seen).toContain('fast:error')
    expect(seen).not.toContain('slow:ok')
    slow.resolve(1)
    await p
  })

  it('onUpdate receives the final state object contents', async () => {
    const onUpdate = vi.fn()
    await loadAnalyses({
      siteId: 's', cache: createResultCache(), onUpdate,
      specs: [{ kind: 'k', params: {}, run: () => Promise.resolve('d') }],
    })
    expect(onUpdate).toHaveBeenCalledWith('k', { status: 'loading' })
    expect(onUpdate).toHaveBeenLastCalledWith('k', { status: 'ok', data: 'd', fromCache: false })
  })

  it('onUpdate is optional', async () => {
    await expect(loadAnalyses({
      siteId: 's', cache: createResultCache(),
      specs: [{ kind: 'k', params: {}, run: () => Promise.resolve(1) }],
    })).resolves.toBeTruthy()
  })

  it('sites do not share cache entries', async () => {
    const cache = createResultCache()
    const run = vi.fn().mockResolvedValue(1)
    await loadAnalyses({ siteId: 'A', cache, specs: [{ kind: 'k', params: {}, run }] })
    await loadAnalyses({ siteId: 'B', cache, specs: [{ kind: 'k', params: {}, run }] })
    expect(run).toHaveBeenCalledTimes(2)
  })
})
