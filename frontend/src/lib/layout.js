// Sidebar sizing rules shared by the splitter, the map and persisted state.
export const SIDEBAR_MIN = 280
export const SIDEBAR_DEFAULT = 350
const STORAGE_KEY = 'sidebarWidth'
const KEY_STEP = 16

export const sidebarMax = (viewportWidth) => Math.max(SIDEBAR_MIN, Math.floor(viewportWidth * 0.7))

export function clampSidebarWidth(width, viewportWidth) {
  const w = Number.isFinite(width) ? Math.round(width) : SIDEBAR_DEFAULT
  return Math.min(sidebarMax(viewportWidth), Math.max(SIDEBAR_MIN, w))
}

export function nextWidthForKey(key, width, viewportWidth) {
  switch (key) {
    case 'ArrowLeft': return clampSidebarWidth(width - KEY_STEP, viewportWidth)
    case 'ArrowRight': return clampSidebarWidth(width + KEY_STEP, viewportWidth)
    case 'Home': return SIDEBAR_MIN
    case 'End': return sidebarMax(viewportWidth)
    default: return null
  }
}

// The map grows in proportion to the sidebar so a wider pane gives a bigger map.
export const mapHeightForWidth = (width) => Math.min(640, Math.max(240, Math.round((width * 240) / 350)))

export function loadSidebarWidth(storage, viewportWidth) {
  try {
    const raw = storage?.getItem(STORAGE_KEY)
    return clampSidebarWidth(raw == null || raw === '' ? NaN : Number(raw), viewportWidth)
  } catch {
    return clampSidebarWidth(NaN, viewportWidth)
  }
}

export function saveSidebarWidth(storage, width) {
  try {
    storage?.setItem(STORAGE_KEY, String(width))
  } catch {
    /* storage unavailable — width just won't persist */
  }
}
