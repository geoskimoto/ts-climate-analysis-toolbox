"""Orchestration for the SNOTEL snow analysis.

Mirrors :mod:`api.service` (streamflow) but computes snow-appropriate metrics —
peak SWE, April-1 SWE, and melt-out date — sharing the water-year / climatology
/ hydrograph helpers in :mod:`api.common`.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date

import pandas as pd

from climate_core import DataLoader, NRCSSnotel, Snow
from climate_core.catalog import default_snotel_catalog

from api import schemas
from api.common import (
    attach_dowy,
    build_climatology,
    build_hydrograph,
    day_of_water_year,
    mk,
    trim_to_complete_water_years,
)

VALUE_LABEL = "SWE"
UNITS = "in"
ELEMENT = "WTEQ"  # snow water equivalent

_CACHE: "OrderedDict[tuple, pd.DataFrame]" = OrderedDict()
_CACHE_MAX = 32


def _fetch_raw(triplet: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    key = (triplet, start_date, end_date)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    df = NRCSSnotel().get_data(
        begin_date=start_date, end_date=end_date, station_triplets=triplet, elements=[ELEMENT]
    )
    _CACHE[key] = df
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return df


def clear_cache() -> None:
    _CACHE.clear()


def run_snow_analysis(req: schemas.SnowAnalysisRequest) -> schemas.SnowAnalysisResult:
    catalog = default_snotel_catalog()
    station = catalog.get(req.station_triplet)  # KeyError -> 404

    start = (req.start_date or date(1970, 10, 1)).isoformat()
    end = (req.end_date or date.today()).isoformat()

    raw = _fetch_raw(station.station_triplet, start, end)
    if raw is None or raw.empty:
        raise ValueError(f"No SNOTEL data for {station.station_triplet} in {start}..{end}.")
    if ELEMENT not in raw.columns:
        raise ValueError(f"SNOTEL station {station.station_triplet} returned no {ELEMENT} data.")

    raw = raw[["Date", ELEMENT]].copy()
    raw = trim_to_complete_water_years(raw, "Date", req.min_days_per_water_year)
    if raw.empty:
        raise ValueError(
            f"No complete water years (>= {req.min_days_per_water_year} days) for "
            f"{station.station_triplet} in {start}..{end}."
        )

    s = Snow(DataLoader(raw, "Date", ELEMENT))
    dowy_by_month_day = attach_dowy(s, ELEMENT)

    # --- metrics --------------------------------------------------------- #
    s.calc_max(window_size=1, alpha=req.alpha)
    peak_swe = _build_peak_swe(s)

    s.calc_benchmark_swe(req.benchmark_month_day, alpha=req.alpha)
    april1 = schemas.BenchmarkSwe(
        benchmark_month_day=req.benchmark_month_day,
        mk=mk(s.benchmark_swe_mann_kendall_test),
        points=[
            schemas.ValuePoint(water_year=int(wy), value=float(v))
            for wy, v in s.benchmark_swe_df[ELEMENT].items()
        ],
    )

    s.calc_melt_out_date(alpha=req.alpha)
    melt_out = _build_melt_out(s)

    climatology = build_climatology(s, dowy_by_month_day)
    hydrograph = build_hydrograph(s, ELEMENT) if req.include_hydrograph else None

    water_years = sorted(int(wy) for wy in s._df["Water Year"].unique())
    meta = schemas.SnowAnalysisMeta(
        station=schemas.SnotelSiteOut(**station.to_dict()),
        value_label=VALUE_LABEL,
        units=UNITS,
        record_start=str(s._df["Date"].min().date()),
        record_end=str(s._df["Date"].max().date()),
        n_water_years=len(water_years),
        water_years=water_years,
    )

    return schemas.SnowAnalysisResult(
        meta=meta,
        climatology=climatology,
        peak_swe=peak_swe,
        april1_swe=april1,
        melt_out=melt_out,
        hydrograph=hydrograph,
    )


def _build_peak_swe(s: Snow) -> schemas.SnowPeak:
    maxs = s.rolling_yr_maxs.drop_duplicates("Water Year", keep="first")
    points = [
        schemas.PeakPoint(
            water_year=int(row["Water Year"]),
            day_of_year=day_of_water_year(pd.Timestamp(row["Date"]), int(row["Water Year"])),
            value=float(row[ELEMENT]),
        )
        for _, row in maxs.iterrows()
    ]
    points.sort(key=lambda p: p.water_year)
    return schemas.SnowPeak(
        mk_magnitude=mk(s.rolling_yr_Qmax_mk_test),
        mk_timing=mk(s.rolling_yr_DOYmax_mk_test),
        points=points,
    )


def _build_melt_out(s: Snow) -> schemas.MeltOut:
    points = []
    for wy, row in s.melt_out_df.iterrows():
        dt = pd.Timestamp(row["date"])
        points.append(
            schemas.TimingPoint(
                water_year=int(wy),
                day_of_year=int(row["dayofwateryear"]),
                date=str(dt.date()),
                month_day=dt.strftime("%m-%d"),
            )
        )
    points.sort(key=lambda p: p.water_year)
    return schemas.MeltOut(mk=mk(s.melt_out_mann_kendall_test), points=points)
