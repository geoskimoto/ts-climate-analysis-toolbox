import { describe, it, expect, vi, afterEach } from 'vitest'
import { getDefaults } from '../src/api.js'

afterEach(() => vi.unstubAllGlobals())

describe('getDefaults', () => {
  it('GETs /api/defaults and resolves the JSON body', async () => {
    const body = { start_date: '1985-10-01', end_date: '2025-09-30' }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => body })
    vi.stubGlobal('fetch', fetchMock)
    await expect(getDefaults()).resolves.toEqual(body)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0][0]).toBe('/api/defaults')
    const init = fetchMock.mock.calls[0][1]
    expect(!init || !init.method || init.method === 'GET').toBe(true)
  })

  it('rejects with the server detail on HTTP error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 500, statusText: 'Server Error', json: async () => ({ detail: 'db offline' }),
    }))
    await expect(getDefaults()).rejects.toThrow('db offline')
  })

  it('rejects with statusText when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
      ok: false, status: 502, statusText: 'Bad Gateway', json: async () => { throw new Error('not json') },
    }))
    await expect(getDefaults()).rejects.toThrow('Bad Gateway')
  })

  it('propagates network failures as rejections', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(getDefaults()).rejects.toThrow('Failed to fetch')
  })
})
