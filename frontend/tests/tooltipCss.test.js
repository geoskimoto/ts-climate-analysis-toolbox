// NOTE: weak by nature. This reads styles.css as plain text and checks the
// .leaflet-tooltip rule(s) allow wrapping and cap width; it cannot prove the
// tooltip actually renders correctly in a browser (verify manually).
import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const css = readFileSync(resolve(__dirname, '../src/styles.css'), 'utf8')
const rules = [...css.matchAll(/(^|\})\s*([^{}]*\.leaflet-tooltip[^{}]*)\{([^}]*)\}/g)].map((m) => m[3])
const body = rules.join('\n')

describe('.leaflet-tooltip styling', () => {
  it('has at least one rule', () => expect(rules.length).toBeGreaterThan(0))
  it('allows text wrapping (white-space: normal or pre-wrap)', () => {
    expect(body).toMatch(/white-space\s*:\s*(normal|pre-wrap)/)
  })
  it('declares a max-width', () => expect(body).toMatch(/max-width\s*:/))
})
