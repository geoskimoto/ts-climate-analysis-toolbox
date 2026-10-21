import { useRef } from 'react'
import { SIDEBAR_DEFAULT, SIDEBAR_MIN, clampSidebarWidth, nextWidthForKey, sidebarMax } from '../lib/layout'

// Draggable divider between the sidebar and the analysis pane. The sidebar
// starts at the window's left edge, so the pointer's clientX is the new width.
export default function Splitter({ width, onChange, viewportWidth }) {
  const dragging = useRef(false)

  const onPointerDown = (e) => {
    dragging.current = true
    e.currentTarget.setPointerCapture?.(e.pointerId)
    document.body.classList.add('is-resizing')
  }
  const onPointerMove = (e) => {
    if (dragging.current) onChange(clampSidebarWidth(e.clientX, viewportWidth))
  }
  const stop = (e) => {
    if (!dragging.current) return
    dragging.current = false
    e.currentTarget.releasePointerCapture?.(e.pointerId)
    document.body.classList.remove('is-resizing')
  }
  const onKeyDown = (e) => {
    const next = nextWidthForKey(e.key, width, viewportWidth)
    if (next == null) return
    e.preventDefault()
    onChange(next)
  }

  return (
    <div
      className="splitter"
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize sidebar"
      tabIndex={0}
      aria-valuenow={width}
      aria-valuemin={SIDEBAR_MIN}
      aria-valuemax={sidebarMax(viewportWidth)}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={stop}
      onPointerCancel={stop}
      onKeyDown={onKeyDown}
      onDoubleClick={() => onChange(SIDEBAR_DEFAULT)}
    />
  )
}
