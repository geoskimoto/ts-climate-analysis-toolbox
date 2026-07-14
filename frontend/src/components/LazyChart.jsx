import { useRef, useState, useEffect } from 'react'

const MARGIN = 300 // px before the viewport at which a chart starts mounting

// Mounts its children (a Plotly chart) only once the slot is at/near the
// viewport, so a chart-heavy page renders its plots as you reach them instead
// of all at once. Once shown it stays mounted (no re-init thrash on scroll).
//
// Robust across environments: a synchronous rect check mounts anything already
// in view on first paint (no dependency on IntersectionObserver firing), and a
// capture-phase scroll/resize listener is kept as a fallback next to the
// observer so mounting still works where IO callbacks don't fire.
export default function LazyChart({ height = 300, children }) {
  const ref = useRef(null)
  const [shown, setShown] = useState(false)

  useEffect(() => {
    if (shown) return
    const el = ref.current
    if (!el) return

    const inView = () => {
      const r = el.getBoundingClientRect()
      const vh = window.innerHeight || document.documentElement.clientHeight
      return r.top < vh + MARGIN && r.bottom > -MARGIN
    }

    let done = false
    const reveal = () => {
      if (done) return
      done = true
      setShown(true)
    }
    const check = () => {
      if (inView()) reveal()
    }

    // 1) Immediate check — mounts charts already on screen without waiting.
    check()
    if (done) return

    // 2) IntersectionObserver (efficient path in normal browsers).
    let obs
    if (typeof IntersectionObserver !== 'undefined') {
      obs = new IntersectionObserver(
        (entries) => entries.some((e) => e.isIntersecting) && reveal(),
        { rootMargin: `${MARGIN}px 0px` },
      )
      obs.observe(el)
    }

    // 3) Scroll/resize fallback (capture phase catches nested scroll containers).
    window.addEventListener('scroll', check, true)
    window.addEventListener('resize', check)

    return () => {
      obs?.disconnect()
      window.removeEventListener('scroll', check, true)
      window.removeEventListener('resize', check)
    }
  }, [shown])

  return (
    <div ref={ref} style={{ minHeight: height }}>
      {shown ? children : <div className="chart-skeleton" style={{ height }} aria-hidden="true" />}
    </div>
  )
}
