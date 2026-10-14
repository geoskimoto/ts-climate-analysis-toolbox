"""Orchestration for the baseflow (hydrograph separation) analysis.

Fetches daily discharge through the shared USGS cache, runs the
``climate_core.stats.baseflow`` public API per requested method and assembles
the response. Route handlers stay thin; everything testable lives here.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from climate_core.catalog import default_catalog
from climate_core.catalog.regulation import regulation_hint
from climate_core.stats import baseflow as bf

from api import schemas, service

MIN_WATER_YEARS = 10

METHOD_LABELS = {
    "lyne_hollick": "Lyne-Hollick filter",
    "local_minimum": "Local minimum (HYSEP-style)",
}

CAVEATS = [
    "Baseflow here is hydrograph-separation baseflow, a filter-defined slow component "
    "of streamflow, not measured groundwater discharge.",
    "Snowmelt, bank storage and reservoir releases can be counted as baseflow.",
    "Trends over about 30 water years are sensitive to the start and end years of the window; "
    "report a range across methods, not a single value.",
]

METRIC_INFO = [
    ("bfi", "Baseflow index", "-", "Baseflow volume divided by total flow volume over the water year."),
    ("baseflow_af", "Annual baseflow volume", "acre-ft", "Total baseflow over the water year."),
    ("junjul_baseflow_cfs", "Jun-Jul mean baseflow", "cfs", "Mean baseflow, June 1 to July 31."),
    ("augsep_baseflow_cfs", "Aug-Sep mean baseflow", "cfs", "Mean baseflow, August 1 to September 30 (late-summer low flow)."),
    ("min7_baseflow_cfs", "7-day minimum baseflow", "cfs", "Minimum 7-day rolling mean of baseflow over the water year."),
    ("baseflow_cot_dowy", "Baseflow center of timing", "day of water year",
     "First day of water year (Oct 1 = 1) by which half of the annual baseflow volume has passed."),
    ("recession_k", "Recession constant", "-", "Median daily baseflow ratio b[t]/b[t-1] on falling days, Jul 15 to Oct 31."),
]
METRIC_KEYS = [m[0] for m in METRIC_INFO]


def _num(v) -> float | None:
    """Finite float or None (NaN/inf/None -> None)."""
    if v is None:
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _label(method: str, bfi_max: float) -> str:
    if method == "eckhardt":
        return f"Eckhardt filter (BFImax={bfi_max:.2f})"
    return METHOD_LABELS[method]


def _area(site) -> float | None:
    a = _num(site.drainage_area_sqmi)
    # SPEC-GAP: a non-positive catalog area is treated like a missing one.
    return a if a is not None and a > 0 else None


def _separate(method: str, q: np.ndarray, area: float | None, bfi_max: float) -> np.ndarray:
    if method == "lyne_hollick":
        return bf.lyne_hollick(q)
    if method == "eckhardt":
        return bf.eckhardt(q, bfi_max=bfi_max)
    return bf.local_minimum(q, area)


def _trend_test(d: dict) -> schemas.TrendTest:
    return schemas.TrendTest(**{k: (_num(v) if k not in ("trend", "significant") else v) for k, v in d.items()})


def _hamed_rao(d: dict) -> schemas.HamedRao:
    return schemas.HamedRao(
        trend=d["trend"], significant=d["significant"],
        p_value=_num(d["p_value"]), tau=_num(d["tau"]), slope=_num(d["slope"]),
    )


def _trends(raw: dict) -> dict[str, schemas.BaseflowTrend | None]:
    out: dict[str, schemas.BaseflowTrend | None] = {}
    for key in METRIC_KEYS:
        t = raw.get(key)
        out[key] = None if t is None else schemas.BaseflowTrend(
            original=_trend_test(t["original"]),
            hamed_rao=_hamed_rao(t["hamed_rao"]),
            slope_pct_per_decade=_num(t["slope_pct_per_decade"]),
        )
    return out


def _quality(rep: bf.QualityReport) -> schemas.BaseflowQuality:
    return schemas.BaseflowQuality(
        n_interpolated=int(rep.n_interpolated),
        skipped_runs=[
            schemas.SkippedRun(start=str(a.date()), end=str(b.date())) for a, b in rep.skipped_runs
        ],
        excluded_water_years=[
            schemas.ExcludedWaterYear(water_year=int(wy), reason=r)
            for wy, r in sorted(rep.excluded_water_years.items())
        ],
    )


def _example(series: pd.Series, wy: int, methods: list[str], area: float | None, bfi_max: float):
    """Observed flow and per-method baseflow for one water year.

    Baseflow comes from the same cleaned (<=3-day-gap-interpolated) series and
    the same contiguous run the metrics used.
    """
    # SPEC-GAP: reuses the stats module's private cleaning helpers so the
    # example is guaranteed to match the metrics' data policy (DRY).
    clean, _, _ = bf._prepare(series)
    days = pd.date_range(f"{wy - 1}-10-01", f"{wy}-09-30", freq="D")
    pos = clean.index.get_indexer(days)
    run = next(
        (r for r in bf._contiguous_runs(~clean.isna().to_numpy()) if r[0] <= pos[0] and pos[-1] <= r[1]),
        None,
    )
    if run is None:  # unreachable for a complete water year
        raise ValueError(f"Water year {wy} is not inside a filtered run.")
    start, end = run
    q_run = clean.to_numpy()[start: end + 1]
    lo, hi = pos[0] - start, pos[-1] - start + 1
    observed = series.where(series >= 0).reindex(days)
    return schemas.BaseflowExample(
        water_year=wy,
        dates=[str(d.date()) for d in days],
        flow_cfs=[_num(v) for v in observed.to_numpy()],
        baseflow_cfs={
            m: [_num(v) for v in _separate(m, q_run, area, bfi_max)[lo:hi]] for m in methods
        },
    )


def run_baseflow_analysis(req: schemas.BaseflowRequest) -> schemas.BaseflowResult:
    site = default_catalog().get(req.site_no)  # KeyError -> 404 in the route
    start, end = req.start_date.isoformat(), req.end_date.isoformat()

    raw = service._fetch_raw(site.site_no, start, end)
    if raw is None or raw.empty:
        raise ValueError(f"No data returned for site {site.site_no} in {start}..{end}.")

    dates = pd.to_datetime(raw["Date"])
    series = pd.Series(raw["Discharge"].to_numpy(dtype=float), index=pd.DatetimeIndex(dates))

    area = _area(site)
    skipped, per_method, results = [], {}, []
    for method in req.methods:
        if method == "local_minimum" and area is None:
            skipped.append(schemas.SkippedMethod(
                method=method, reason="Drainage area is missing in the site catalog (needed for the window length)."
            ))
            continue
        kwargs = {"bfi_max": req.eckhardt_bfi_max} if method == "eckhardt" else {}
        df, rep = bf.water_year_metrics(series, method, drainage_area_sqmi=area, **kwargs)
        if not per_method and len(df) < MIN_WATER_YEARS:
            raise ValueError(
                f"Need at least {MIN_WATER_YEARS} complete water years for the baseflow trend "
                f"analysis; found {len(df)} for site {site.site_no} in {start}..{end}."
            )
        per_method[method] = df
        results.append(schemas.BaseflowMethodResult(
            method=method,
            label=_label(method, req.eckhardt_bfi_max),
            quality=_quality(rep),
            metrics=[
                schemas.BaseflowYearMetrics(
                    water_year=int(row["water_year"]),
                    **{k: _num(row[k]) for k in METRIC_KEYS},
                )
                for _, row in df.iterrows()
            ],
            trends=_trends(bf.baseflow_trends(df, alpha=req.alpha)),
        ))
    if not per_method:
        raise ValueError("No requested baseflow method could be run: " + "; ".join(
            f"{s.method}: {s.reason}" for s in skipped))

    water_years = [r.water_year for r in results[0].metrics]
    example_wy = req.example_water_year if req.example_water_year is not None else water_years[-1]
    if example_wy not in water_years:
        raise ValueError(
            f"example_water_year {example_wy} is not a complete water year in the results "
            f"({water_years[0]}-{water_years[-1]})."
        )

    rng = bf.method_range(per_method, alpha=req.alpha).reindex(METRIC_KEYS)
    method_range = [
        schemas.BaseflowRangeRow(
            metric=metric,
            min=_num(r["min"]), median=_num(r["median"]), max=_num(r["max"]),
            n_sig_decreasing=int(r["n_sig_decreasing"]),
            n_sig_increasing=int(r["n_sig_increasing"]),
            n_methods=int(r["n_methods"]),
        )
        for metric, r in rng.iterrows()
    ]

    hint = regulation_hint(site.name, site.drainage_area_sqmi)
    d = dates.dt
    meta = schemas.BaseflowMeta(
        site=schemas.SiteOut(**site.to_dict()),
        units="cfs",
        window_start=start,
        window_end=end,
        record_start=str(d.date.min()),
        record_end=str(d.date.max()),
        water_years=water_years,
        eckhardt_bfi_max=req.eckhardt_bfi_max,
        alpha=req.alpha,
        regulation=schemas.RegulationOut(level=hint.level, reason=hint.reason),
        caveats=list(CAVEATS),
    )
    return schemas.BaseflowResult(
        meta=meta,
        metric_info=[
            schemas.BaseflowMetricInfo(key=k, label=lab, unit=u, description=desc)
            for k, lab, u, desc in METRIC_INFO
        ],
        methods=results,
        method_range=method_range,
        skipped_methods=skipped,
        example=_example(series, example_wy, list(per_method), area, req.eckhardt_bfi_max),
    )
