const NOTES = {
  regulated: 'This gauge is regulated — trends here mostly reflect reservoir or diversion operations, not climate.',
  likely_regulated: 'This gauge is likely regulated — treat trends with caution; operations may dominate the climate signal.',
}

export const streamflowRegulationNote = (level) => NOTES[level] ?? null
