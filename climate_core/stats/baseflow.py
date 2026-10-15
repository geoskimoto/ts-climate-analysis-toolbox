"""Baseflow separation and per-water-year baseflow metrics with MK trends.

Hydrograph-separation baseflow is the slowly varying component of daily mean
discharge *as defined by each method*; it is not a direct groundwater
measurement. Three pure-numpy separation filters are provided
(:func:`lyne_hollick`, :func:`eckhardt`, :func:`local_minimum`), plus
:func:`water_year_metrics` (explicit, logged data-quality policy),
:func:`baseflow_trends` (Mann-Kendall / Hamed-Rao + Sen's slope per year) and
:func:`method_range` (spread across methods -- report ranges, never one value).

Conventions: discharge in cfs, water year = 1 Oct - 30 Sep labelled by the
ending calendar year, volumes in acre-feet. See ``docs/baseflow_spec.md``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd
from pymannkendall import hamed_rao_modification_test, original_test
from scipy.stats import theilslopes

from climate_core.stats.mk import mk_to_dict

METHODS = ("lyne_hollick", "eckhardt", "local_minimum")

_CFS_DAY_TO_AF = 1.9835          # 1 cfs sustained for one day, in acre-feet
_MAX_GAP_DAYS = 3                # gaps <= this are linearly interpolated
_MIN_RUN_DAYS = 365              # shorter contiguous runs are not filtered
_MAX_INTERP_FRAC = 0.01          # WY excluded if more of its days were filled
_REFLECT = 30                    # Lyne-Hollick end reflection length
_MIN_TREND_YEARS = 10

_METRIC_COLUMNS = [
    "water_year",
    "bfi",
    "baseflow_af",
    "junjul_baseflow_cfs",
    "augsep_baseflow_cfs",
    "min7_baseflow_cfs",
    "baseflow_cot_dowy",
    "recession_k",
]


@dataclass
class QualityReport:
    """What the data-quality policy did to the input series."""

    n_interpolated: int = 0                                   # days filled by the <=3-day rule
    skipped_runs: list[tuple[pd.Timestamp, pd.Timestamp]] = field(default_factory=list)
    excluded_water_years: dict[int, str] = field(default_factory=dict)
    # interpolated days per full-coverage water year examined (incl. excluded ones)
    n_interpolated_by_wy: dict[int, int] = field(default_factory=dict)


# --------------------------------------------------------------------------
# Separation methods
# --------------------------------------------------------------------------
def _check_unit_open(name: str, value: float) -> None:
    if not 0.0 < value < 1.0:
        raise ValueError(f"{name} must be in (0, 1), got {value}")


def _lh_pass(x: np.ndarray, alpha: float) -> np.ndarray:
    """One forward Lyne-Hollick pass; returns the baseflow of ``x``."""
    qf = 0.0
    out = np.empty_like(x)
    out[0] = x[0]
    k = (1.0 + alpha) / 2.0
    for t in range(1, len(x)):
        qf = alpha * qf + k * (x[t] - x[t - 1])
        qf = min(max(qf, 0.0), x[t])
        out[t] = x[t] - qf
    return out


def lyne_hollick(q: np.ndarray, alpha: float = 0.925, passes: int = 3) -> np.ndarray:
    """Lyne-Hollick recursive digital filter (Nathan & McMahon, 1990).

    ``q`` is reflected by 30 values at both ends, filtered ``passes`` times
    (forward, backward, forward, ...; each pass filters the previous pass's
    baseflow) and trimmed. Returns baseflow with ``0 <= b <= q``.
    """
    _check_unit_open("alpha", alpha)
    if passes < 1:
        raise ValueError(f"passes must be >= 1, got {passes}")
    q = np.asarray(q, dtype=float)
    if q.ndim != 1 or len(q) < _REFLECT + 1:
        raise ValueError(f"lyne_hollick needs a 1-D series of at least {_REFLECT + 1} values")
    x = np.pad(q, _REFLECT, mode="reflect")
    for i in range(passes):
        if i % 2 == 0:
            x = _lh_pass(x, alpha)
        else:
            x = _lh_pass(x[::-1], alpha)[::-1]
    return np.clip(x[_REFLECT:-_REFLECT], 0.0, q)


def eckhardt(q: np.ndarray, alpha: float = 0.98, bfi_max: float = 0.80) -> np.ndarray:
    """Eckhardt (2005) two-parameter recursive filter.

    Recommended ``bfi_max``: 0.80 perennial / porous aquifer, 0.50 ephemeral /
    porous, 0.25 perennial / hard rock.
    """
    _check_unit_open("alpha", alpha)
    _check_unit_open("bfi_max", bfi_max)
    q = np.asarray(q, dtype=float)
    b = np.empty_like(q)
    if len(q) == 0:
        return b
    b[0] = min(q[0], bfi_max * q[0])
    denom = 1.0 - alpha * bfi_max
    for t in range(1, len(q)):
        val = ((1.0 - bfi_max) * alpha * b[t - 1] + (1.0 - alpha) * bfi_max * q[t]) / denom
        b[t] = min(val, q[t])
    return b


def _hysep_window(drainage_area_sqmi: float) -> int:
    """Odd window length 2N* (ties go to the larger odd integer), in [3, 11]."""
    if not drainage_area_sqmi > 0:
        raise ValueError("drainage_area_sqmi must be > 0")
    two_n = 2.0 * 0.8 * drainage_area_sqmi ** 0.2
    lo = 2 * int(np.floor((two_n - 1.0) / 2.0)) + 1      # odd integer at or below two_n
    nearest = lo + 2 if two_n - lo >= 1.0 else lo
    return int(min(max(nearest, 3), 11))


def local_minimum(q: np.ndarray, drainage_area_sqmi: float) -> np.ndarray:
    """USGS HYSEP local-minimum method (Sloto & Crouse, 1996)."""
    q = np.asarray(q, dtype=float)
    n = len(q)
    if n == 0:
        return q.copy()
    half = (_hysep_window(drainage_area_sqmi) - 1) // 2
    idx = np.arange(n)
    # Window truncated at the series ends (SPEC 7b).
    is_min = np.array([q[i] <= q[max(0, i - half): i + half + 1].min() for i in idx])
    mins = idx[is_min]
    b = np.interp(idx, mins, q[mins])        # holds nearest minimum outside the ends
    return np.minimum(b, q)


_SEPARATORS: dict[str, Callable[..., np.ndarray]] = {
    "lyne_hollick": lyne_hollick,
    "eckhardt": eckhardt,
}


# --------------------------------------------------------------------------
# Data-quality preparation
# --------------------------------------------------------------------------
def _prepare(
    series: pd.Series, max_gap_days: int = _MAX_GAP_DAYS
) -> tuple[pd.Series, np.ndarray, int]:
    """Daily-reindex ``series``; blank negatives; fill gaps <= ``max_gap_days``.

    Returns (clean series with NaN for long gaps, interpolated-flag array,
    n_interpolated).
    """
    if not isinstance(series.index, pd.DatetimeIndex):
        raise ValueError("series must have a DatetimeIndex")
    if series.index.has_duplicates:
        raise ValueError("series index contains duplicate dates")
    s = series.astype(float).sort_index()
    s = s.copy()
    s[s < 0] = np.nan                                     # negative discharge == missing
    if len(s) == 0:
        return s, np.zeros(0, dtype=bool), 0
    s = s.reindex(pd.date_range(s.index.min(), s.index.max(), freq="D"))

    isna = s.isna().to_numpy()
    filled = np.zeros(len(s), dtype=bool)
    i, n = 0, len(s)
    while i < n:
        if not isna[i]:
            i += 1
            continue
        j = i
        while j < n and isna[j]:
            j += 1
        # interior gap short enough to fill (needs a valid value on both sides)
        if i > 0 and j < n and (j - i) <= max_gap_days:
            filled[i:j] = True
        i = j
    if filled.any():
        interp = s.interpolate(method="linear", limit_area="inside")
        s = s.where(~filled, interp)
    return s, filled, int(filled.sum())


def _contiguous_runs(valid: np.ndarray) -> list[tuple[int, int]]:
    """Inclusive (start, end) positions of runs of True."""
    runs, i, n = [], 0, len(valid)
    while i < n:
        if not valid[i]:
            i += 1
            continue
        j = i
        while j < n and valid[j]:
            j += 1
        runs.append((i, j - 1))
        i = j
    return runs


def _wy_metrics(
    dates: pd.DatetimeIndex,
    q: np.ndarray,
    b: np.ndarray,
    filled: np.ndarray | None = None,
    min_window_coverage: float | None = None,
) -> dict:
    """Metrics for one complete water year (arrays aligned with ``dates``).

    With ``min_window_coverage`` set, a window metric is NaN when the observed
    (non-interpolated) fraction of its window is below that value.
    """
    sum_q, sum_b = q.sum(), b.sum()
    month = dates.month
    day = dates.day
    # SPEC-GAP: bfi / centre-of-timing are undefined when the WY has zero total
    # flow (0/0); NaN is returned rather than inventing a value.
    bfi = sum_b / sum_q if sum_q > 0 else np.nan
    if sum_b > 0:
        cot = int(np.argmax(np.cumsum(b) >= 0.5 * sum_b)) + 1      # Oct 1 = DOWY 1
    else:
        cot = np.nan
    min7 = pd.Series(b).rolling(7).mean().min()

    rec_window = ((month == 7) & (day >= 15)) | (month == 8) | (month == 9) | (month == 10)
    t = np.flatnonzero(rec_window)
    t = t[t > 0]
    falling = t[b[t] < b[t - 1]]
    # b[t] < b[t-1] implies b[t-1] > 0, so the ratio is always defined.
    k = float(np.median(b[falling] / b[falling - 1])) if len(falling) >= 10 else np.nan

    def covered(mask: np.ndarray) -> bool:
        if min_window_coverage is None or filled is None:
            return True
        return 1.0 - filled[mask].mean() >= min_window_coverage

    all_days = np.ones(len(dates), dtype=bool)
    nan = float("nan")
    return {
        "bfi": float(bfi),
        "baseflow_af": float(sum_b * _CFS_DAY_TO_AF),
        "junjul_baseflow_cfs": float(b[(month == 6) | (month == 7)].mean()) if covered((month == 6) | (month == 7)) else nan,
        "augsep_baseflow_cfs": float(b[(month == 8) | (month == 9)].mean()) if covered((month == 8) | (month == 9)) else nan,
        "min7_baseflow_cfs": float(min7) if covered(all_days) else nan,
        "baseflow_cot_dowy": cot,
        "recession_k": k if covered(rec_window) else nan,
    }


def water_year_metrics(
    series: pd.Series,
    method: str,
    drainage_area_sqmi: float | None = None,
    *,
    max_gap_days: int = _MAX_GAP_DAYS,
    max_interp_frac: float = _MAX_INTERP_FRAC,
    min_window_coverage: float | None = None,
    **method_kwargs,
) -> tuple[pd.DataFrame, QualityReport]:
    """Per-water-year baseflow metrics for a daily-mean discharge series (cfs).

    Applies the data-quality policy of the spec (gaps <= 3 days interpolated
    and counted, longer gaps split runs, runs < 365 days skipped, incomplete
    or > 1 % interpolated water years excluded with a reason). Returns one row
    per complete water year (columns as in spec section 5, RangeIndex) and a
    :class:`QualityReport`.

    Policy knobs (spec 3b; defaults reproduce v1): ``max_gap_days`` (>= 1),
    ``max_interp_frac`` in [0, 1) (WY excluded if its interpolated fraction is
    greater), ``min_window_coverage`` in (0, 1] or None (window metrics become
    NaN when the observed fraction of their window is lower).
    """
    if max_gap_days < 1:
        raise ValueError("max_gap_days must be >= 1")
    if not 0.0 <= max_interp_frac < 1.0:
        raise ValueError("max_interp_frac must be in [0, 1)")
    if min_window_coverage is not None and not 0.0 < min_window_coverage <= 1.0:
        raise ValueError("min_window_coverage must be in (0, 1]")
    if method not in METHODS:
        raise ValueError(f"unknown method {method!r}; expected one of {METHODS}")
    if method == "local_minimum" and drainage_area_sqmi is None:
        raise ValueError("drainage_area_sqmi is required for method 'local_minimum'")

    s, filled, n_interp = _prepare(series, max_gap_days)
    report = QualityReport(n_interpolated=n_interp)
    if len(s) == 0:
        return pd.DataFrame(columns=_METRIC_COLUMNS), report

    if method == "local_minimum":
        def separate(x: np.ndarray) -> np.ndarray:
            return local_minimum(x, drainage_area_sqmi, **method_kwargs)
    else:
        def separate(x: np.ndarray) -> np.ndarray:
            return _SEPARATORS[method](x, **method_kwargs)

    q_all = s.to_numpy()
    b_all = np.full(len(s), np.nan)
    in_run = np.zeros(len(s), dtype=bool)
    for start, end in _contiguous_runs(~np.isnan(q_all)):
        if end - start + 1 < _MIN_RUN_DAYS:
            report.skipped_runs.append((s.index[start], s.index[end]))
            continue
        b_all[start: end + 1] = separate(q_all[start: end + 1])
        in_run[start: end + 1] = True

    first, last = s.index[0], s.index[-1]
    wy_of = lambda ts: ts.year + (1 if ts.month >= 10 else 0)   # noqa: E731
    rows = []
    for wy in range(wy_of(first), wy_of(last) + 1):
        wy_days = pd.date_range(f"{wy - 1}-10-01", f"{wy}-09-30", freq="D")
        if wy_days[0] < first or wy_days[-1] > last:
            report.excluded_water_years[wy] = "series does not cover the full water year"
            continue
        pos = s.index.get_indexer(wy_days)
        n_fill = int(filled[pos].sum())
        report.n_interpolated_by_wy[wy] = n_fill
        if not in_run[pos].all():
            report.excluded_water_years[wy] = (
                "contains days outside a filtered run (gap > 3 days or run < 365 days)"
            )
            continue
        frac = n_fill / len(wy_days)
        if frac > max_interp_frac:
            report.excluded_water_years[wy] = (
                f"{n_fill} of {len(wy_days)} days interpolated ({frac * 100:.1f}%) "
                f"exceeds {max_interp_frac * 100:g}%"
            )
            continue
        rows.append({"water_year": wy, **_wy_metrics(wy_days, q_all[pos], b_all[pos], filled[pos], min_window_coverage)})

    df = pd.DataFrame(rows, columns=_METRIC_COLUMNS).reset_index(drop=True)
    return df, report


# --------------------------------------------------------------------------
# Trends and cross-method summary
# --------------------------------------------------------------------------
def baseflow_trends(metrics: pd.DataFrame, alpha: float = 0.10) -> dict[str, dict | None]:
    """Mann-Kendall (original and Hamed-Rao) trends for each metric column.

    Value is ``None`` when a metric has fewer than 10 non-null years. Otherwise
    ``{"original", "hamed_rao", "slope_pct_per_decade"}``. Years must be
    ascending and unique (gaps allowed). Sen's slope for
    ``slope_pct_per_decade`` is ``scipy.stats.theilslopes(y, x=water_year)``,
    i.e. per year. The ``slope`` field inside the ``mk_to_dict`` outputs is
    pymannkendall's per-index slope and equals a per-year slope only when the
    years are consecutive.
    """
    _check_unit_open("alpha", alpha)
    years = metrics["water_year"].to_numpy()
    if len(years) > 1 and not np.all(np.diff(years) > 0):
        raise ValueError("water_year must be sorted ascending and unique")

    out: dict[str, dict | None] = {}
    for col in metrics.columns:
        if col == "water_year":
            continue
        y_ser = metrics[col].astype(float)
        ok = y_ser.notna().to_numpy()
        if ok.sum() < _MIN_TREND_YEARS:
            out[col] = None
            continue
        y, x = y_ser.to_numpy()[ok], years[ok].astype(float)
        sen = float(theilslopes(y, x=x)[0])
        med = float(np.median(y))
        pct = sen * 10.0 / med * 100.0 if med != 0 else float("nan")
        out[col] = {
            "original": mk_to_dict(original_test(y, alpha=alpha)),
            "hamed_rao": mk_to_dict(hamed_rao_modification_test(y, alpha=alpha)),
            "slope_pct_per_decade": float(pct),
        }
    return out


def method_range(per_method: dict[str, pd.DataFrame], alpha: float = 0.10) -> pd.DataFrame:
    """Spread of each metric's period mean across separation methods.

    Index = metric; columns ``min``, ``median``, ``max`` (nan-aware, over the
    per-method period means), ``n_sig_decreasing`` / ``n_sig_increasing``
    (methods whose original MK test is significant at ``alpha`` with that
    sign) and ``n_methods``.
    """
    # SPEC-GAP: n_methods is taken as the number of frames supplied, not the
    # number with a non-NaN mean for the metric.
    metrics: list[str] = []
    for df in per_method.values():
        metrics += [c for c in df.columns if c != "water_year" and c not in metrics]
    trends = {m: baseflow_trends(df, alpha) for m, df in per_method.items()}

    rows = {}
    for metric in metrics:
        means = np.array(
            [df[metric].mean() if metric in df.columns else np.nan for df in per_method.values()],
            dtype=float,
        )
        have = means[~np.isnan(means)]
        lo, med, hi = ((float(have.min()), float(np.median(have)), float(have.max()))
                       if len(have) else (np.nan, np.nan, np.nan))
        dec = inc = 0
        for t in trends.values():
            res = t.get(metric)
            if res and res["original"]["significant"]:
                dec += res["original"]["trend"] == "decreasing"
                inc += res["original"]["trend"] == "increasing"
        rows[metric] = {
            "min": lo, "median": med, "max": hi,
            "n_sig_decreasing": int(dec), "n_sig_increasing": int(inc),
            "n_methods": len(per_method),
        }
    cols = ["min", "median", "max", "n_sig_decreasing", "n_sig_increasing", "n_methods"]
    return pd.DataFrame.from_dict(rows, orient="index", columns=cols)
