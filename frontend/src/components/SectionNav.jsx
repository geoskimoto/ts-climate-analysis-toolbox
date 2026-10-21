// Sticky in-page links that jump to an analysis section.
export default function SectionNav({ sections, active, onNavigate }) {
  return (
    <nav className="section-nav" aria-label="Analysis sections">
      {sections.map((s) => (
        <button
          key={s.id}
          type="button"
          className={`section-nav__btn ${active === s.id ? 'section-nav__btn--active' : ''}`}
          aria-current={active === s.id ? 'true' : undefined}
          onClick={() => onNavigate(s.id)}
        >
          {s.label}
        </button>
      ))}
    </nav>
  )
}
