import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SectionShell from '../src/components/SectionShell.jsx'

const child = <div data-testid="child">content</div>

describe('SectionShell', () => {
  it('renders a section with id, labelled by its h2 title, and a divider', () => {
    const { container } = render(<SectionShell id="baseflow" title="Baseflow" status="ok">{child}</SectionShell>)
    const section = container.querySelector('section#baseflow')
    expect(section).not.toBeNull()
    const h2 = screen.getByRole('heading', { level: 2, name: 'Baseflow' })
    expect(h2.id).toBeTruthy()
    expect(section.getAttribute('aria-labelledby')).toBe(h2.id)
    expect(screen.getByTestId('section-divider')).toBeInTheDocument()
  })
  it('loading: shows progress text and no children', () => {
    render(<SectionShell id="x" title="T" status="loading">{child}</SectionShell>)
    expect(screen.getByText(/computing|loading|fetching/i)).toBeInTheDocument()
    expect(screen.queryByTestId('child')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
  })
  it('error: shows role=alert with the error text and a working Retry', async () => {
    const onRetry = vi.fn()
    render(<SectionShell id="x" title="T" status="error" error="upstream timed out" onRetry={onRetry}>{child}</SectionShell>)
    expect(screen.getByRole('alert')).toHaveTextContent('upstream timed out')
    expect(screen.queryByTestId('child')).toBeNull()
    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })
  it('ok: renders children and no alert', () => {
    render(<SectionShell id="x" title="T" status="ok">{child}</SectionShell>)
    expect(screen.getByTestId('child')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByRole('button', { name: 'Retry' })).toBeNull()
  })
  it.each(['idle', undefined])('status %s: only the heading, no children/alert/retry', (status) => {
    render(<SectionShell id="x" title="T" status={status}>{child}</SectionShell>)
    expect(screen.getByRole('heading', { level: 2, name: 'T' })).toBeInTheDocument()
    expect(screen.queryByTestId('child')).toBeNull()
    expect(screen.queryByRole('alert')).toBeNull()
    expect(screen.queryByRole('button')).toBeNull()
  })
})
