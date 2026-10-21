import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import Splitter from '../src/components/Splitter.jsx'
import { SIDEBAR_MIN, SIDEBAR_DEFAULT, sidebarMax } from '../src/lib/layout.js'

describe('Splitter', () => {
  it('exposes separator semantics with value range', () => {
    render(<Splitter width={400} onChange={() => {}} viewportWidth={1200} />)
    const s = screen.getByRole('separator')
    expect(s).toHaveAttribute('aria-orientation', 'vertical')
    expect(s).toHaveAttribute('aria-label', expect.stringMatching(/resize/i))
    expect(s).toHaveAttribute('tabindex', '0')
    expect(s).toHaveAttribute('aria-valuenow', '400')
    expect(s).toHaveAttribute('aria-valuemin', String(SIDEBAR_MIN))
    expect(s).toHaveAttribute('aria-valuemax', String(sidebarMax(1200)))
  })
  it('is focusable via keyboard', async () => {
    render(<Splitter width={400} onChange={() => {}} viewportWidth={1200} />)
    await userEvent.tab()
    expect(screen.getByRole('separator')).toHaveFocus()
  })
  it.each([
    ['ArrowLeft', 384], ['ArrowRight', 416], ['Home', 280], ['End', 840],
  ])('%s calls onChange(%i) and prevents default', (key, expected) => {
    const onChange = vi.fn()
    render(<Splitter width={400} onChange={onChange} viewportWidth={1200} />)
    const notPrevented = fireEvent.keyDown(screen.getByRole('separator'), { key })
    expect(onChange).toHaveBeenCalledTimes(1)
    expect(onChange).toHaveBeenCalledWith(expected)
    expect(notPrevented).toBe(false)
  })
  it('clamps at the limits', () => {
    const onChange = vi.fn()
    render(<Splitter width={282} onChange={onChange} viewportWidth={1200} />)
    fireEvent.keyDown(screen.getByRole('separator'), { key: 'ArrowLeft' })
    expect(onChange).toHaveBeenCalledWith(280)
  })
  it('ignores other keys without preventing default', () => {
    const onChange = vi.fn()
    render(<Splitter width={400} onChange={onChange} viewportWidth={1200} />)
    const notPrevented = fireEvent.keyDown(screen.getByRole('separator'), { key: 'a' })
    fireEvent.keyDown(screen.getByRole('separator'), { key: 'Tab' })
    expect(onChange).not.toHaveBeenCalled()
    expect(notPrevented).toBe(true)
  })
  it('double-click resets to SIDEBAR_DEFAULT', async () => {
    const onChange = vi.fn()
    render(<Splitter width={500} onChange={onChange} viewportWidth={1200} />)
    await userEvent.dblClick(screen.getByRole('separator'))
    expect(onChange).toHaveBeenCalledWith(SIDEBAR_DEFAULT)
  })
})
