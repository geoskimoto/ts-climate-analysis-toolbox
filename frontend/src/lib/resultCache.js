// Order-independent, nested-safe serialisation so equal params share a key.
function stable(v) {
  if (Array.isArray(v)) return `[${v.map(stable).join(',')}]`
  if (v && typeof v === 'object') {
    return `{${Object.keys(v).sort().map((k) => `${JSON.stringify(k)}:${stable(v[k])}`).join(',')}}`
  }
  return JSON.stringify(v) ?? 'undefined'
}

export function createResultCache() {
  const store = new Map()
  const key = (kind, siteId, params) => JSON.stringify([kind, siteId, stable(params)])
  return {
    get: (kind, siteId, params) => store.get(key(kind, siteId, params)),
    set: (kind, siteId, params, value) => { store.set(key(kind, siteId, params), value) },
    clear: () => store.clear(),
    clearSite(siteId) {
      for (const k of [...store.keys()]) if (JSON.parse(k)[1] === siteId) store.delete(k)
    },
  }
}
