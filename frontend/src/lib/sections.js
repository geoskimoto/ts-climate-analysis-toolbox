export const SECTIONS = [
  { id: 'streamflow', label: 'Streamflow' },
  { id: 'baseflow', label: 'Baseflow' },
]

// `tops`: section id -> bounding-rect top (px from viewport top). Active is the
// last section that has scrolled to/above the offset, else the first.
export function pickActiveSection(tops, offset = 80) {
  let active = SECTIONS[0].id
  for (const { id } of SECTIONS) {
    if (id in tops && tops[id] <= offset) active = id
  }
  return active
}
