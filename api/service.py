"""Orchestration between the HTTP layer and ``climate_core``.

Fetches (and caches) raw USGS data, trims to complete water years, runs the
Streamflow metrics, and assembles the response payload. Keeping this out of the
route handlers keeps ``main.py`` thin and this logic unit-testable.
"""

from __future__ import annotations

from collections import OrderedDict
from datetime import date

import pandas as pd

from climate_core import DataLoader, Streamflow, USGSStreamflow
from climate_core.catalog import default_catalog

from api import schemas
from api.common import (
    attach_dowy,
    build_climatology,
    build_hydrograph,
    mk,
    trim_to_complete_water_years,
)

# Discharge in cfs; volumes reported in million acre-feet (maf).
VALUE_LABEL = "Discharge"
UNITS = "cfs"

# --------------------------------------------------------------------------- #
# Raw-fetch cache (simple bounded LRU of DataFrames — fine for a local tool).
# --------------------------------------------------------------------------- #
_CACHE: "OrderedDict[tuple, pd.DataFrame]" = OrderedDict()
_CACHE_MAX = 32


def _fetch_raw(site_no: str, start_date: str, end_date: str) -> pd.DataFrame:
    key = (site_no, start_date, end_date)
    if key in _CACHE:
        _CACHE.move_to_end(key)
        return _CACHE[key]
    df = USGSStreamflow().get_data(sites=site_no, start_date=start_date, end_date=end_date)
    _CACHE[key] = df
    _CACHE.move_to_end(key)
    while len(_CACHE) > _CACHE_MAX:
        _CACHE.popitem(last=False)
    return df


def clear_cache() -> None:
    _CACHE.clear()


# --------------------------------------------------------------------------- #
# Main entry point
# --------------------------------------------------------------------------- #
def run_analysis(req: schemas.AnalysisRequest) -> schemas.AnalysisResult:
    catalog = default_catalog()
    site = catalog.get(req.site_no)  # raises KeyError -> 404 in the route

    start = (req.start_date or date(1900, 10, 1)).isoformat()
    end = (req.end_date or date.today()).isoformat()

    raw = _fetch_raw(site.site_no, start, end)
    if raw is None or raw.empty:
        raise ValueError(f"No data returned for site {site.site_no} in {start}..{end}.")

    raw = trim_to_complete_water_years(raw, "Date", req.min_days_per_water_year)
    if raw.empty:
        raise ValueError(
            f"No complete water years (>= {req.min_days_per_water_year} days) "
            f"for site {site.site_no} in {start}..{end}."
        )

    s = Streamflow(DataLoader(raw, "Date", "Discharge"))
    dowy_by_month_day = attach_dowy(s, "Discharge")

    windows = req.seasonal_windows or schemas.DEFAULT_SEASONAL_WINDOWS

    # --- metrics --------------------------------------------------------- #
    s.calc_annual_runoff_threshold_day(percent=req.threshold_percent, alpha=req.alpha)
    center_of_timing = _build_center_of_timing(s, req.threshold_percent)
    total_volume = _build_total_volume(s)

    seasonal_volumes = []
    for w in windows:
        s.calc_runoff_bw_days(w.begin_month_day, w.end_month_day, alpha=req.alpha)
        seasonal_volumes.append(
            schemas.SeasonalVolume(
                label=w.label,
                begin_month_day=w.begin_month_day,
                end_month_day=w.end_month_day,
                mk=mk(s.volume_bw_days_mann_kendall_test),
                points=[
                    schemas.VolumePoint(water_year=int(wy), volume_maf=float(v))
                    for wy, v in s.volume_bw_days_df["Discharge"].items()
                ],
            )
        )

    s.calc_max(
        window_size=req.peak_window_size,
        alpha=req.alpha,
        ignore_winter_months=req.ignore_winter_months,
    )
    peak = _build_peak(s, req)

    climatology = build_climatology(s, dowy_by_month_day)
    hydrograph = build_hydrograph(s, "Discharge") if req.include_hydrograph else None

    water_years = sorted(int(wy) for wy in s._df["Water Year"].unique())
    meta = schemas.AnalysisMeta(
        site=schemas.SiteOut(**site.to_dict()),
        value_label=VALUE_LABEL,
        units=UNITS,
        record_start=str(s._df["Date"].min().date()),
        record_end=str(s._df["Date"].max().date()),
        n_water_years=len(water_years),
        water_years=water_years,
    )

    return schemas.AnalysisResult(
        meta=meta,
        climatology=climatology,
        center_of_timing=center_of_timing,
        total_volume=total_volume,
        seasonal_volumes=seasonal_volumes,
        peak=peak,
        hydrograph=hydrograph,
    )


# --------------------------------------------------------------------------- #
# Payload builders
# --------------------------------------------------------------------------- #
def _build_center_of_timing(s: Streamflow, pct: float) -> schemas.CenterOfTiming:
    date_col = f"{pct * 100}%_volume_point_date"
    df = s.threshold_vol_stats
    points = []
    for wy, dt in df[date_col].items():
        dt = pd.Timestamp(dt)
        points.append(
            schemas.TimingPoint(
                water_year=int(wy),
                day_of_year=dt.timetuple().tm_yday,
                date=str(dt.date()),
                month_day=dt.strftime("%m-%d"),
            )
        )
    points.sort(key=lambda p: p.water_year)
    return schemas.CenterOfTiming(
        threshold_percent=pct,
        mk_timing=mk(s.threshold_vol_dates_mann_kendall_test),
        mk_volume=mk(s.threshold_vol_mann_kendall_test),
        points=points,
    )


def _build_total_volume(s: Streamflow) -> schemas.TotalVolume:
    points = [
        schemas.VolumePoint(water_year=int(wy), volume_maf=float(v))
        for wy, v in s.threshold_vol_stats["total_volume"].items()
    ]
    points.sort(key=lambda p: p.water_year)
    return schemas.TotalVolume(mk=mk(s.total_volume_mann_kendall_test), points=points)


def _build_peak(s: Streamflow, req: schemas.AnalysisRequest) -> schemas.Peak:
    maxs = s.rolling_yr_maxs.drop_duplicates("Water Year", keep="first")
    points = [
        schemas.PeakPoint(
            water_year=int(row["Water Year"]),
            day_of_year=int(row["dayofyear"]),
            value=float(row["Discharge"]),
        )
        for _, row in maxs.iterrows()
    ]
    points.sort(key=lambda p: p.water_year)
    return schemas.Peak(
        window_size=req.peak_window_size,
        ignore_winter_months=req.ignore_winter_months,
        mk_magnitude=mk(s.rolling_yr_Qmax_mk_test),
        mk_timing=mk(s.rolling_yr_DOYmax_mk_test),
        points=points,
    )
