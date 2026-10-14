# Baseflow mode in the explorer app: implementation plan and API contract

Status: PLAN v1 (user approved "add baseflow to the app", 2026-10-14). Branch `feat/baseflow`. Depends on `climate_core/stats/baseflow.py` (done; see `docs/baseflow_spec.md`).

## Scope
A third mode, **Baseflow (USGS)**, beside Streamflow and Snowpack. For one USGS gauge (live USGS fetch via the existing cache in `api.service._fetch_raw`; DB-backed source and MT/BC catalog are a later follow-up) it runs hydrograph-separation baseflow with up to three methods and shows per-water-year metrics, Mann-Kendall trends, the across-method range, an example-year hydrograph, and mandatory caveats. Default window **WY1996-WY2025** (project decision; earlier records were anomalous).

Out of scope: DB data source, MT/BC gauges, snow pairing, precomputation of all sites (few internal users; existing LRU cache is enough).

## Steps (commit after each)
1. **Plan + contract** (this file).
2. **Backend tests first** (separate test-author agent, from this contract only): `tests/test_regulation_hint.py`, `tests/test_api_baseflow.py` (network-free: monkeypatch `api.service._fetch_raw`), `tests/test_service_baseflow.py`. Lock.
3. **Backend implementation** (different agent): `climate_core/catalog/regulation.py`, `api/service_baseflow.py`, schemas in `api/schemas.py`, route in `api/main.py`. Must not edit tests.
4. **Frontend** (implementation agent; no JS test framework exists and none is added): `BaseflowControls.jsx`, `BaseflowView.jsx`, `api.js` (`analyzeBaseflow`), `App.jsx` tab + params. Verify with `npm run build` and a manual browser/screenshot check against a running API.
5. Independent mutation pass on the new Python code; docs/README update; findings.md update.

## Regulation hint: `climate_core/catalog/regulation.py`
`regulation_hint(name: str | None, drainage_area_sqmi: float | None) -> RegulationHint` where `RegulationHint` is a frozen dataclass `(level: str, reason: str)`.
Rules (same heuristic as `HUC17_subbasin_resaearch/analysis/baseflow_pipeline.py:regulation_flag`; the analysis should import this later - tracked as follow-up):
- Upper-cased name matches any of the word-boundary patterns `DAM`, `BELOW`, `BL`, `RESERVOIR(S)`, `CANAL(S)`, `DIVERSION(S)`, `FLUME(S)`, `LAKE OUTLET`, `WASTEWAY`, `OUTLET OF ... (LAKE|RESERVOIR)`, `AT ... DAM` -> `level="likely_regulated"`, reason names the matched pattern text.
- Else drainage area numeric, finite, `0 < A < 200` mi2 -> `"likely_unregulated"`.
- Else `"unknown"`. None/NaN/non-numeric area -> unknown. The reason string always says it is a name/size heuristic, not verified.

## API: `POST /api/analyze/baseflow`
### Request `BaseflowRequest`
| field | type | default | validation |
|---|---|---|---|
| `site_no` | str | required | 404 if not in catalog |
| `start_date` | date or null | 1995-10-01 | |
| `end_date` | date or null | 2025-09-30 | `start_date < end_date` else 422 |
| `methods` | list of `"lyne_hollick" \| "eckhardt" \| "local_minimum"` | all three | non-empty, unique else 422 |
| `eckhardt_bfi_max` | float | 0.80 | strictly in (0,1) else 422 |
| `alpha` | float | 0.10 | strictly in (0,1) else 422 |
| `example_water_year` | int or null | null -> latest complete WY | must be a complete WY in results else 422 |

### Behaviour
- Fetch daily discharge (cfs) with `api.service._fetch_raw(site_no, start, end)` (reuse the cache); unknown site -> 404; empty -> 422 `"No data returned ..."`; requests errors -> 502 (as other routes).
- Build a float `pd.Series` indexed by date; run `water_year_metrics` for each requested method (`local_minimum` needs the catalog `drainage_area_sqmi`; if missing, the method is **skipped**, listed in `skipped_methods`, not an error; if every requested method is skipped -> 422).
- Fewer than 10 complete water years for the first successfully-run method -> 422 `"Need at least 10 complete water years ..."`.
- `baseflow_trends(metrics, alpha)` per method; `method_range` across the methods that ran.
- Non-finite floats (NaN/inf) are returned as JSON `null`, never as NaN tokens.
- `caveats` always contains at least: baseflow is hydrograph-separation baseflow, not measured groundwater; snowmelt, bank storage and reservoir releases can be counted as baseflow; trends over ~30 water years are sensitive to the start/end years.

### Response `BaseflowResult` (JSON)
```
meta: { site: SiteOut, units: "cfs", window_start: str(date), window_end: str(date),
        record_start: str, record_end: str, water_years: [int],   # complete WYs of the first method that ran
        eckhardt_bfi_max: float, alpha: float,
        regulation: {level: str, reason: str}, caveats: [str] }
metric_info: [ {key: str, label: str, unit: str, description: str} ]   # one per metric in spec section 5, in spec order
methods: [ { method: str, label: str,
             quality: { n_interpolated: int,
                        skipped_runs: [ {start: str, end: str} ],
                        excluded_water_years: [ {water_year: int, reason: str} ] },
             metrics: [ { water_year: int, bfi: float|null, baseflow_af: float|null, junjul_baseflow_cfs: ..., augsep_baseflow_cfs: ...,
                          min7_baseflow_cfs: ..., baseflow_cot_dowy: ..., recession_k: ... } ],   # ascending water_year
             trends: { <metric_key>: null | { original: MannKendall, hamed_rao: HamedRao, slope_pct_per_decade: float|null } } } ]
method_range: [ { metric: str, min: float|null, median: float|null, max: float|null,
                  n_sig_decreasing: int, n_sig_increasing: int, n_methods: int } ]
skipped_methods: [ { method: str, reason: str } ]
example: { water_year: int, dates: [str], flow_cfs: [float|null], baseflow_cfs: { <method>: [float|null] } }  # Oct 1-Sep 30 of that WY, same length per series
```
`MannKendall` = existing schema (trend, significant, p_value, z, tau, s, var_s, slope, intercept). `HamedRao` = `{trend: str, significant: bool, p_value: float|null, tau: float|null, slope: float|null}` (p may be null when pymannkendall returns NaN).
`label` strings: `"Lyne-Hollick filter"`, `"Eckhardt filter (BFImax=0.80)"` (shows the used value), `"Local minimum (HYSEP-style)"`.
`example.baseflow_cfs` is computed by running the separation function on the **same cleaned series** the metrics used (interpolated values included) and slicing the example water year.

## Clarifications (added after test authoring)
- `original` uses a permissive `TrendTest` shape `{trend: str, significant: bool, p_value: float|null, z: float|null, tau: float|null, s: float|null, var_s: float|null, slope: float|null, intercept: float|null}` (replaces "original: MannKendall"); `hamed_rao` keeps the 5-key `HamedRao` shape `{trend, significant, p_value: float|null, tau: float|null, slope: float|null}`. Any non-finite value is serialized as null. (User decision 2026-10-14: the earlier draft here that gave `hamed_rao` all 9 keys was an error and is reverted.)
- Explicit `null` for `start_date`/`end_date` means the default.
- `methods` in the response follow the request order, minus skipped ones; `method_range` rows follow `metric_info` order.
- `record_start`/`record_end` are the min/max dates of the raw fetched series (before any water-year trimming).
- Absent dates in the fetched frame are treated as gaps (handled by the stats module's gap policy).
- Errors: service raises `KeyError` (unknown site) and `ValueError` (everything else, including pydantic `ValidationError`); the route maps them to 404/422 like the existing routes; `requests.RequestException` -> 502.
- `network`-marked tests are excluded with `pytest -m "not network"` per the README (no addopts).

## Frontend contract
- New source tab "Baseflow (USGS)" in `App.jsx`; reuses the streamflow site list/map (same catalog), STATES list `['', 'WA', 'OR', 'ID']`.
- `DEFAULT_BASEFLOW_PARAMS = { start_date: '1995-10-01', end_date: '2025-09-30', methods: [all three], eckhardt_bfi_max: 0.8, alpha: 0.1 }`.
- `BaseflowControls`: start/end dates, method checkboxes (at least one), BFImax, alpha, Run button.
- `BaseflowView`: (1) caveat banner (always visible) + regulation badge (likely regulated -> amber warning; unknown/unregulated -> neutral note); (2) method-range table (metric, min/median/max across methods, counts of methods with significant decrease/increase) with the sentence "report a range, not a single value"; (3) metric selector (default `augsep_baseflow_cfs`) driving a trend chart that overlays one series per method (distinct colorblind-safe colors and marker shapes) using water year on x; Sen's-slope verdict cards (reuse `MannKendallCard`) per method for the selected metric, showing both original and Hamed-Rao significance and `slope_pct_per_decade`; (4) example-year hydrograph: observed flow (solid) with each method's baseflow (distinct dashed styles), axis "Discharge (cfs)"; (5) quality notes per method (excluded water years with reasons).
- Axes labelled with units; direction never conveyed by color alone (reuse arrow glyphs); null values render as gaps; friendly error banner for 404/422/502.
- Build must pass `npm run build`; no new JS dependencies or build tools.

## Risks / open items
- Live USGS fetch for 30 years can take several seconds; the UI shows the existing "fetching" placeholder.
- Hamed-Rao NaN p-values (library behaviour, ~1.7% of cases) are mapped to `null`; UI shows "n/a".
- The streamflow mode's default `start_date` is still 1930-10-01; left unchanged (out of scope), flagged for the user.
- Duplicate regulation heuristic exists in the analysis project; follow-up: make the analysis import this one.
