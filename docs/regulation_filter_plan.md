# Regulated vs unregulated site filter: contract

Status: PLAN v1 (user request 2026-10-15: "add the regulated vs unregulated filter to the app"). Builds on `docs/regulated_gauges_plan.md` (curated list + `regulation_hint`) and `docs/baseflow_app_plan.md`.

## Goal
In the Streamflow (USGS) and Baseflow (USGS) modes let the user filter the site list and map by regulation class, and see regulation at a glance on every site. (Snowpack mode has no regulation concept and shows no filter.)

## Backend
### Response fields (additive; existing fields and behaviour unchanged)
`GET /api/sites` and `GET /api/sites/{site_no}` return `SiteWithRegulation` = existing `SiteOut` fields plus:
- `regulation_level: str` one of `regulated | likely_regulated | likely_unregulated | unknown`
- `regulation_reason: str` the `reason` from `regulation_hint`
Computed with `climate_core.catalog.regulation.regulation_hint(name, drainage_area_sqmi, site_no=site_no)` (curated list > name pattern > small area > unknown). `SiteOut` itself, and every other route that uses it (analysis meta, paired view), stay unchanged.

### Query parameter on `GET /api/sites`
`regulation` (optional): comma-separated list of levels, e.g. `regulation=regulated,likely_regulated`. Whitespace around items is ignored; empty items are ignored; duplicates are fine. Unknown level names -> HTTP 422 with a detail naming the bad value(s). An empty string (or absent) means no filter. Filtering is applied together with the existing `query`, `state`, `basin` filters (AND) and BEFORE `limit`. Ordering of results is unchanged.

### Helper
`climate_core/catalog/regulation.py` (or a small new module) exposes `REGULATION_LEVELS: tuple[str, ...] = ("regulated", "likely_regulated", "likely_unregulated", "unknown")` as the single source of truth for valid levels; `regulation_hint` must only ever return these.

## Frontend
- A "Regulation" filter group in the sidebar for the streamflow and baseflow modes (hidden in snow mode), three toggle chips (multi-select, all on by default, at least one must stay on): **Regulated** (= regulated + likely_regulated), **Unregulated** (= likely_unregulated), **Unknown**. Each chip shows its count within the current state/search filter. Clicking filters the list AND the map (client-side using `regulation_level` from the API; the API param exists for other clients).
- Map markers encode regulation by more than colour: regulated = filled orange-vermilion with a thick dark ring; unregulated = filled blue; unknown = hollow grey ring. A small legend under the map explains them. The selected-site styling is unchanged.
- List items show a small text badge ("Regulated", "Likely regulated", "Unregulated", or none for unknown) with a tooltip of `regulation_reason`.
- Counts of "N sites" in the list header reflect all active filters.
- Friendly behaviour: if `regulation_level` is missing (old API), treat the site as unknown and hide the filter.
- No new dependencies; Okabe-Ito colours; keyboard-focusable chips with `aria-pressed`.

## Process
1. Contract (this file). 2. Backend tests by a separate agent (`tests/test_sites_regulation.py`), locked. 3. Backend implementation by another agent. 4. Frontend by a third agent, verified in a real browser. 5. Commit and push to `feat/baseflow`; the user runs `deploy_baseflow.sh`.
