import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import SectionNav from '../src/components/SectionNav.jsx'

const sections = [{ id: 'streamflow', label: 'Streamflow' }, { id: 'baseflow', label: 'Baseflow' }]

describe('SectionNav', () => {
  it('renders a labelled nav landmark with one button per section', () => {
    render(<SectionNav sections={sections} active="streamflow" onNavigate={() => {}} />)
    const nav = screen.getByRole('navigation', { name: 'Analysis sections' })
    expect(nav).toBeInTheDocument()
    const buttons = screen.getAllByRole('button')
    expect(buttons.map((b) => b.textContent)).toEqual(['Streamflow', 'Baseflow'])
    buttons.forEach((b) => expect(b).toHaveAttribute('type', 'button'))
  })
  it('marks only the active section with aria-current="true"', () => {
    render(<SectionNav sections={sections} active="baseflow" onNavigate={() => {}} />)
    expect(screen.getByRole('button', { name: 'Baseflow' })).toHaveAttribute('aria-current', 'true')
    expect(screen.getByRole('button', { name: 'Streamflow' })).not.toHaveAttribute('aria-current')
  })
  it('calls onNavigate with the section id on click', async () => {
    const onNavigate = vi.fn()
    render(<SectionNav sections={sections} active="streamflow" onNavigate={onNavigate} />)
    await userEvent.click(screen.getByRole('button', { name: 'Baseflow' }))
    expect(onNavigate).toHaveBeenCalledTimes(1)
    expect(onNavigate).toHaveBeenCalledWith('baseflow')
  })
})
