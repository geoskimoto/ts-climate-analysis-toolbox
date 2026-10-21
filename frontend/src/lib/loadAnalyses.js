// Run several analyses for one site independently: cached ones return at once,
// the rest start in parallel, and one failure never affects another.
export async function loadAnalyses({ siteId, specs, cache, onUpdate }) {
  const notify = (kind, state) => onUpdate?.(kind, state)
  const entries = await Promise.all(
    specs.map(async ({ kind, params, run }) => {
      const hit = cache.get(kind, siteId, params)
      if (hit !== undefined) {
        const state = { status: 'ok', data: hit, fromCache: true }
        return [kind, state]
      }
      notify(kind, { status: 'loading' })
      let state
      try {
        const data = await run(params)
        cache.set(kind, siteId, params, data)
        state = { status: 'ok', data, fromCache: false }
      } catch (e) {
        state = { status: 'error', error: e?.message ?? String(e) }
      }
      notify(kind, state)
      return [kind, state]
    }),
  )
  return Object.fromEntries(entries)
}
