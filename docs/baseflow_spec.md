# Baseflow module specification (`climate_core/stats/baseflow.py`)

Status: SPEC v1 (locked once tests are written). Tests are written from this document by an agent that does not implement the module; the implementer must not edit tests.

## 1. Purpose
Hydrograph-separation baseflow and per-water-year metrics with Mann-Kendall trend tests, mirroring `climate_core/stats/streamflow.py`. Baseflow here means the slowly varying component of daily mean discharge as defined by each separation method. It is NOT a direct groundwater measurement (it cannot distinguish groundwater from slow snowmelt, bank storage, or reservoir releases).

## 2. Conventions
- Input: daily mean discharge in **cfs** (convert cms -> cfs with 35.3147 before calling; unit handling belongs to the loader).
- Water year (WY): 1 Oct - 30 Sep, labelled by the ending calendar year. Day-of-water-year (DOWY): Oct 1 = 1 (as `api.common.day_of_water_year`).
- Default analysis window: WY1996-WY2025 (30 water years). Earlier years are out of scope for this project; the module itself accepts any window.
- Volumes are reported in **acre-feet (af)**: 1 cfs sustained for one day = 1.9835 af. (`Streamflow` uses a different unit scheme; this module does not reuse it.) Units are explicit in column names (`_cfs`, `_af`).

## 3. Data quality policy (explicit, logged, no silent fills)
- Series must be a daily DatetimeIndex with no duplicates. Duplicates raise `ValueError`.
- Negative or NaN discharge is "missing". Zero is valid.
- Gaps of <= 3 consecutive missing days are linearly interpolated; each interpolation is counted and reported in `QualityReport.n_interpolated`. Longer gaps split the series into contiguous runs.
- Each run must be >= 365 days to be filtered; shorter runs are reported in `QualityReport.skipped_runs`.
- A water year is **complete** only if all its days lie inside a filtered run (after the <=3-day interpolation) and <= 1% of its days were interpolated. Incomplete water years are excluded from metrics and listed in `QualityReport.excluded_water_years` with a reason. Nothing is dropped silently.

## 4. Separation methods (pure functions, numpy in/out, same length as input)
All return baseflow `b` with `0 <= b <= q` elementwise, `b` finite for finite `q`.

### 4.1 `lyne_hollick(q, alpha=0.925, passes=3)`
Nathan & McMahon (1990). Reflect 30 values at both ends before filtering and trim afterwards. Quickflow filter, forward pass: `qf[t] = alpha*qf[t-1] + (1+alpha)/2 * (q[t]-q[t-1])`, with `qf[t] = max(qf[t], 0)` and `qf[t] = min(qf[t], q[t])`; `b = q - qf`. Passes alternate forward, backward, forward (default 3); each later pass filters the previous pass's baseflow.

### 4.2 `eckhardt(q, alpha=0.98, bfi_max=0.80)`
`b[t] = ((1-bfi_max)*alpha*b[t-1] + (1-alpha)*bfi_max*q[t]) / (1 - alpha*bfi_max)`, `b[t] = min(b[t], q[t])`, `b[0] = min(q[0], bfi_max*q[0])`. Recommended `bfi_max`: 0.80 perennial streams / porous aquifer, 0.50 ephemeral / porous, 0.25 perennial / hard rock. `bfi_max` must be in (0, 1) else `ValueError`.

### 4.3 `local_minimum(q, drainage_area_sqmi)`
USGS HYSEP local-minimum. `N = 0.8 * A**0.2` (A in mi^2); `2N*` = the odd integer nearest `2N`, clipped to [3, 11]. A day is a local minimum if its discharge is <= every discharge in the window of `2N*` days centred on it. Baseflow is the linear interpolation between successive local minima; before the first and after the last minimum use the nearest minimum's value; `b = min(b, q)`.

## 5. Per-water-year metrics (`water_year_metrics(series, method, ...)`) -> DataFrame, one row per complete WY
| column | definition |
|---|---|
| `water_year` | int |
| `bfi` | sum(b)/sum(q) over the WY, in [0,1] |
| `baseflow_af` | sum(b) cfs-days x 1.9835 |
| `junjul_baseflow_cfs` | mean b for Jun 1 - Jul 31 |
| `augsep_baseflow_cfs` | mean b for Aug 1 - Sep 30 |
| `min7_baseflow_cfs` | minimum 7-day rolling mean of b over the WY |
| `baseflow_cot_dowy` | first DOWY at which cumulative b >= 50% of the WY baseflow total |
| `recession_k` | median of `b[t]/b[t-1]` over days in Jul 15 - Oct 31 with `b[t] < b[t-1]`; NaN if fewer than 10 such days |
Methods are also exposed via a `method` string: `"lyne_hollick" | "eckhardt" | "local_minimum"`; unknown -> `ValueError`.

## 6. Trend tests (`baseflow_trends(metrics_df, alpha=0.10)`)
For each metric column with >= 10 non-null years: `pymannkendall.original_test` (alpha default 0.10 as in `Streamflow`) AND `hamed_rao_modification_test` (autocorrelation-robust). Return JSON-serialisable dicts via `mk_to_dict`, plus `slope_pct_per_decade` = Sen's slope x 10 / median(metric) x 100 (NaN if median is 0). Fewer than 10 years -> `None` for that metric (not an error). Years must be sorted ascending and unique (`ValueError` otherwise); they may have gaps. The MK statistic is rank-based; **Sen's slope is computed with `scipy.stats.theilslopes(y, x=water_year)` so it is per year, not per index step**, and `slope_pct_per_decade` uses that slope. The `slope` field inside the `mk_to_dict` outputs is pymannkendall's per-index slope and is only per-year when years are consecutive (documented in the docstring).

## 7. Summary across methods (`method_range(per_method_metrics)`)
Given the per-method frames, return for each metric the min, median and max across methods of the period mean, and the number of methods whose MK trend is significant with the same sign. This is the number the project reports ("range, never a single value").

## 7a. Public API (exact signatures; tests target these)
```python
# climate_core/stats/baseflow.py
METHODS = ("lyne_hollick", "eckhardt", "local_minimum")

@dataclass
class QualityReport:
    n_interpolated: int                                   # days filled by the <=3-day rule
    skipped_runs: list[tuple[pd.Timestamp, pd.Timestamp]] # contiguous runs < 365 days (start, end)
    excluded_water_years: dict[int, str]                  # WY -> reason

def lyne_hollick(q: np.ndarray, alpha: float = 0.925, passes: int = 3) -> np.ndarray
def eckhardt(q: np.ndarray, alpha: float = 0.98, bfi_max: float = 0.80) -> np.ndarray
def local_minimum(q: np.ndarray, drainage_area_sqmi: float) -> np.ndarray

def water_year_metrics(series: pd.Series, method: str,
                       drainage_area_sqmi: float | None = None,
                       **method_kwargs) -> tuple[pd.DataFrame, QualityReport]
    # series: float cfs, DatetimeIndex (daily). drainage_area_sqmi required for "local_minimum"
    # (ValueError if missing). DataFrame columns exactly as section 5, index = RangeIndex.

def baseflow_trends(metrics: pd.DataFrame, alpha: float = 0.10) -> dict[str, dict | None]
    # key = metric column (not water_year); value None if < 10 non-null years, else
    # {"original": mk_to_dict(...), "hamed_rao": mk_to_dict(...), "slope_pct_per_decade": float}

def method_range(per_method: dict[str, pd.DataFrame], alpha: float = 0.10) -> pd.DataFrame
    # index = metric; columns: "min", "median", "max" (of per-method period means),
    # "n_sig_decreasing", "n_sig_increasing" (original MK significant at alpha), "n_methods"
```
`Baseflow` convenience class is out of scope for v1 (the app layer will wrap these functions).

## 7b. Clarifications (added after test authoring; do not conflict with the tests)
- `lyne_hollick` with fewer than 31 values raises `ValueError` (30-value reflection needs at least 31 points).
- `local_minimum` near the series ends uses the window truncated to the available days; end days may be local minima under that truncated window.
- A skipped run's `(start, end)` are both inclusive calendar days of the run.
- When `2N` is exactly midway between two odd integers (e.g. 4.0 -> 3 or 5), choose the larger.
- `method_range` ignores NaN period means (uses `numpy.nanmin/nanmedian/nanmax`); a metric with all-NaN means yields NaN.

## 8. Out of scope (v1)
PART, BFI-Standard (Wahl & Wahl) and chemical/tracer separation; regulation detection; snowmelt correction; field significance (done in the analysis, not the module).

## 9. Required test properties (guidance for the test author)
- Constant discharge -> `b == q`, `bfi == 1` for `lyne_hollick` and `local_minimum`; for `eckhardt` the steady-state solution is `b = bfi_max * q` (so `bfi == bfi_max`), which follows from the 4.2 recursion and its `b[0] = bfi_max*q[0]` initialisation.
- Synthetic hydrograph = known exponential baseflow + injected storm pulses -> BFI within stated tolerance of truth (Lyne-Hollick and Eckhardt: +/-0.10; local-minimum: +/-0.15); `0 <= b <= q` always.
- Reflected-end behaviour: first/last 30 values stable, no NaN.
- Gap policy: 3-day gap interpolated and counted; 4-day gap splits the run; WY with >1% interpolation excluded and listed with a reason.
- WY labelling and DOWY correct across Oct 1 boundaries and leap years.
- Metric definitions checked on hand-computable tiny series.
- Trend test: monotone synthetic series -> significant increasing/decreasing; random series with fixed seed -> not significant; < 10 years -> None; `slope_pct_per_decade` sign/scale checked.
- Parameter validation errors (`bfi_max` outside (0,1), alpha outside (0,1), unknown method, duplicate dates).
- Input arrays are not mutated.
