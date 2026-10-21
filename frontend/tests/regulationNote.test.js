import { describe, it, expect } from 'vitest'
import { streamflowRegulationNote } from '../src/lib/regulationNote.js'

describe('streamflowRegulationNote', () => {
  it.each(['regulated', 'likely_regulated'])('returns a regulation note for %s', (lvl) => {
    const n = streamflowRegulationNote(lvl)
    expect(typeof n).toBe('string')
    expect(n.length).toBeGreaterThan(0)
    expect(n).toMatch(/regulat/i)
  })
  it.each(['likely_unregulated', 'unknown', undefined, null, 'garbage'])('returns null for %s', (lvl) => {
    expect(streamflowRegulationNote(lvl)).toBeNull()
  })
})
