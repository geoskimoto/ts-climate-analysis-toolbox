# Curated regulated-gauge list: contract (amends docs/baseflow_app_plan.md)

Status: PLAN v1 (user approved 2026-10-14). Motivation: the name/size heuristic reported "unknown" for the Clearwater River at Orofino although it is regulated by Dworshak Dam, so the baseflow mode showed a confident trend on a regulated river.

## Data file
`climate_core/catalog/data/regulated_gauges.csv` (UTF-8, header row), one row per gauge:
| column | rule |
|---|---|
| `site_no` | USGS site number as a string; must exist in `default_catalog()`; unique |
| `name` | catalog name (informational; must equal the catalog name for that site_no) |
| `regulator` | short text naming the dam/project/operation that regulates flow at or upstream of the gauge, non-empty |
| `kind` | one of `dam_release`, `diversion`, `reservoir_storage`, `canal_or_return_flow`, `multiple` |
| `confidence` | `high` (regulation stated by USGS/agency documentation or unambiguous: the gauge is immediately downstream of a named large dam) or `medium` (strong regulation upstream but diluted by large unregulated inflow, or based on general knowledge) |
| `source_url` | http(s) URL supporting the entry (USGS water data report, agency page, dam page, etc.); blank not allowed for `high` |
Must include these anchors (tests rely on them): `13340000` (Clearwater R at Orofino; Dworshak Dam), `14105700` (Columbia R at The Dalles), `13290450` (Snake R at Hells Canyon Dam), `13206000` (Boise R at Glenwood Bridge; Lucky Peak/Arrowrock/Anderson Ranch). The list is curated, not exhaustive: absence means "not known to be regulated", NOT "unregulated".

## Loader
`climate_core/catalog/regulation.py` adds `regulated_gauges() -> dict[str, RegulatedGauge]` (cached), `RegulatedGauge` frozen dataclass mirroring the columns. Validates on load: required columns, unique site_no, allowed `kind`/`confidence`, non-empty `regulator`, `high` rows have an http(s) `source_url`; violations raise `ValueError` naming the row.

## Hint behaviour (backwards compatible)
`regulation_hint(name, drainage_area_sqmi, site_no=None)`. Precedence: curated list (when `site_no` given and listed) > name pattern > small area > unknown.
- Curated hit: `level="regulated"`, `reason` = `"Known regulation: <regulator> (<kind>, <confidence> confidence; curated list)."`
- Existing levels and reasons unchanged. Calls without `site_no` behave exactly as before (existing locked tests must keep passing).
Levels are now `regulated | likely_regulated | likely_unregulated | unknown`.

## API / UI
- `api/service_baseflow.py` passes `site.site_no` to `regulation_hint`; `meta.regulation.level` may be `"regulated"`; no schema change (level is a free string).
- Frontend: `regulated` renders as a strong (red/amber with icon) warning "Flow is regulated: <reason>. Trends here mostly reflect operations, not climate."; `likely_regulated` stays amber; others neutral.

## Data compilation rules (data agent)
- Only gauges in `default_catalog()`. Target ~80-150 rows covering major regulated mainstems and tributaries in WA/OR/ID (Columbia, Snake, Clearwater, Pend Oreille/Clark Fork/Kootenai gauges in the catalog, Spokane, Yakima, Deschutes/Crooked, Willamette tributaries, Boise/Payette/Owyhee, Umatilla, John Day if any, etc.).
- Every entry verified against at least one real source retrieved this session (USGS site page / water data report remarks, agency or project page); do not guess. When unverified, omit the row. Keep `source_url` real.
- Record unresolved candidates in `docs/regulated_gauges_unresolved.md`.
