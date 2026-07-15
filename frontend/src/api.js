// Thin fetch wrappers over the FastAPI backend.

const LOGIN_URL = 'https://apps.streamflows.org/login'

async function json(res) {
  if (res.status === 401) {
    // Session expired — sign back in through the portal, then return here.
    window.location.assign(`${LOGIN_URL}?next=${encodeURIComponent(window.location.href)}`)
    throw new Error('Your session has expired — redirecting to sign-in…')
  }
  if (!res.ok) {
    let detail = res.statusText
    try {
      detail = (await res.json()).detail || detail
    } catch {
      /* ignore */
    }
    throw new Error(detail)
  }
  return res.json()
}

export function listSites({ query, state } = {}) {
  const params = new URLSearchParams()
  if (query) params.set('query', query)
  if (state) params.set('state', state)
  params.set('limit', '2000')
  return fetch(`/api/sites?${params}`).then(json)
}

export function analyze(request) {
  return fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  }).then(json)
}

export function listSnotelSites({ query, state } = {}) {
  const params = new URLSearchParams()
  if (query) params.set('query', query)
  if (state) params.set('state', state)
  params.set('limit', '2000')
  return fetch(`/api/snotel-sites?${params}`).then(json)
}

export function analyzeSnow(request) {
  return fetch('/api/analyze/snow', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  }).then(json)
}

export function getSnotelCandidates(siteNo, limit = 6) {
  return fetch(`/api/sites/${siteNo}/snotel-candidates?limit=${limit}`).then(json)
}

export function analyzePaired(request) {
  return fetch('/api/analyze/paired', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  }).then(json)
}
