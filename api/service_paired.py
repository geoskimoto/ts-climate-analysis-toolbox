"""Paired snow <-> streamflow basin analysis (option "B").

Runs the snowpack and streamflow trend metrics over the *same* window -- the
water years present in both records -- so the two signals are directly
comparable, then summarises whether they corroborate. Co-registration is the
whole point: comparing a 90-year streamflow trend against a 40-year snow trend
would be misleading, so both are clipped to their shared water years.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from climate_core import DataLoader, Snow, Streamflow
from climate_core.catalog import default_catalog, default_snotel_catalog

from api import schemas, service, service_snow
from api.common import mk, trim_to_complete_water_years

MIN_COMMON_YEARS = 10


def _water_years(df: pd.DataFrame) -> set[int]:
    d = pd.to_datetime(df["Date"])
    wy = d.dt.year.where(d.dt.month < 10, d.dt.year + 1)
    return set(int(y) for y in wy.unique())


def _filter_to_water_years(df: pd.DataFrame, years: set[int]) -> pd.DataFrame:
    d = pd.to_datetime(df["Date"])
    wy = d.dt.year.where(d.dt.month < 10, d.dt.year + 1)
    return df[wy.isin(years)].reset_index(drop=True)


def _series(key, label, unit, kind, warming_direction, mk_result, index_values) -> schemas.TrendSeries:
    points = [schemas.SeriesPoint(water_year=int(wy), value=float(v)) for wy, v in index_values.items()]
    points.sort(key=lambda p: p.water_year)
    return schemas.TrendSeries(
        key=key, label=label, unit=unit, kind=kind,
        warming_direction=warming_direction, mk=mk(mk_result), points=points,
    )


def run_paired_analysis(req: schemas.PairedRequest) -> schemas.PairedResult:
    gage = default_catalog().get(req.site_no)                 # KeyError -> 404
    station = default_snotel_catalog().get(req.station_triplet)

    start = (req.start_date or date(1930, 10, 1)).isoformat()
    end = (req.end_date or date.today()).isoformat()

    q_raw = service._fetch_raw(gage.site_no, start, end)
    swe_raw = service_snow._fetch_raw(station.station_triplet, start, end)
    if q_raw is None or q_raw.empty:
        raise ValueError(f"No streamflow data for gage {gage.site_no}.")
    if swe_raw is None or swe_raw.empty or "WTEQ" not in swe_raw.columns:
        raise ValueError(f"No SWE data for station {station.station_triplet}.")

    q_raw = trim_to_complete_water_years(q_raw, "Date", 350)
    swe_raw = trim_to_complete_water_years(swe_raw[["Date", "WTEQ"]], "Date", 300)

    common = _water_years(q_raw) & _water_years(swe_raw)
    if len(common) < MIN_COMMON_YEARS:
        raise ValueError(
            f"Only {len(common)} overlapping complete water years between "
            f"{gage.site_no} and {station.station_triplet}; need at least {MIN_COMMON_YEARS}."
        )

    q_raw = _filter_to_water_years(q_raw, common)
    swe_raw = _filter_to_water_years(swe_raw, common)

    # --- streamflow (over the common window) ----------------------------- #
    s = Streamflow(DataLoader(q_raw, "Date", "Discharge"))
    s.calc_annual_runoff_threshold_day(percent=req.threshold_percent, alpha=req.alpha)
    date_col = f"{req.threshold_percent * 100}%_volume_point_date"
    ct_doy = s.threshold_vol_stats[date_col].apply(lambda d: pd.Timestamp(d).timetuple().tm_yday)
    streamflow_trends = [
        _series(
            "center_of_timing",
            f"Center of timing ({round(req.threshold_percent * 100)}%)",
            "day of year", "timing", "decreasing",  # earlier = warming
            s.threshold_vol_dates_mann_kendall_test, ct_doy,
        ),
        _series(
            "total_volume", "Total annual volume", "maf", "value", "decreasing",
            s.total_volume_mann_kendall_test, s.threshold_vol_stats["total_volume"],
        ),
    ]

    # --- snow (over the common window) ----------------------------------- #
    snow = Snow(DataLoader(swe_raw, "Date", "WTEQ"))
    snow.calc_max(window_size=1, alpha=req.alpha)
    peak_by_year = snow.rolling_yr_maxs.drop_duplicates("Water Year", keep="first").set_index("Water Year")["WTEQ"]
    snow.calc_benchmark_swe(req.benchmark_month_day, alpha=req.alpha)
    snow_trends = [
        _series(
            "peak_swe", "Peak SWE", "in", "value", "decreasing",
            snow.rolling_yr_Qmax_mk_test, peak_by_year,
        ),
        _series(
            "april1_swe", f"SWE on {req.benchmark_month_day}", "in", "value", "decreasing",
            snow.benchmark_swe_mann_kendall_test, snow.benchmark_swe_df["WTEQ"],
        ),
    ]

    window_years = sorted(common)
    window = schemas.PairedWindow(
        start_water_year=window_years[0],
        end_water_year=window_years[-1],
        n_water_years=len(window_years),
    )
    corroboration = _corroborate(snow_trends, streamflow_trends)

    return schemas.PairedResult(
        gage=schemas.SiteOut(**gage.to_dict()),
        station=schemas.SnotelSiteOut(**station.to_dict()),
        window=window,
        snow_trends=snow_trends,
        streamflow_trends=streamflow_trends,
        corroboration=corroboration,
    )


def _domain_lean(trends) -> tuple[int, int, list[str]]:
    """Return (warming_votes, counter_votes, detail_lines) for one domain's
    significant trends. A trend votes 'warming' when significant and moving in
    its warming direction.
    """
    warming = counter = 0
    details = []
    for t in trends:
        if t.mk is None:
            details.append(f"{t.label}: insufficient data")
        elif not t.mk.significant:
            details.append(f"{t.label}: no significant trend (p={t.mk.p_value:.3f})")
        else:
            is_warming = t.mk.trend == t.warming_direction
            warming += is_warming
            counter += not is_warming
            direction = "earlier" if t.kind == "timing" else t.mk.trend
            details.append(
                f"{t.label}: {direction} — "
                f"{'warming-consistent' if is_warming else 'counter to warming'} (p={t.mk.p_value:.3f})"
            )
    return warming, counter, details


def _corroborate(snow_trends, streamflow_trends) -> schemas.Corroboration:
    """True corroboration needs a significant signal in *both* domains pointing
    the same way — one lone significant trend can't corroborate anything. We say
    so plainly rather than over-claiming.
    """
    snow_w, snow_c, snow_details = _domain_lean(snow_trends)
    flow_w, flow_c, flow_details = _domain_lean(streamflow_trends)
    details = snow_details + flow_details

    snow_signal = snow_w > 0 or snow_c > 0
    flow_signal = flow_w > 0 or flow_c > 0

    def lean(w, c):
        return "warming" if w > c else "counter" if c > w else "split"

    if not snow_signal and not flow_signal:
        return schemas.Corroboration(
            category="inconclusive",
            summary="No statistically significant trends in either snowpack or streamflow over the shared window.",
            details=details,
        )
    if not (snow_signal and flow_signal):
        present = "snowpack" if snow_signal else "streamflow"
        missing = "streamflow" if snow_signal else "snowpack"
        return schemas.Corroboration(
            category="inconclusive",
            summary=(
                f"A significant {present} trend exists but {missing} shows none over the shared window — "
                "not enough to corroborate across domains."
            ),
            details=details,
        )

    snow_lean, flow_lean = lean(snow_w, snow_c), lean(flow_w, flow_c)
    if snow_lean == flow_lean == "warming":
        return schemas.Corroboration(
            category="corroborating",
            summary="Snowpack and streamflow both show a warming-consistent signal over the shared record — they corroborate.",
            details=details,
        )
    if snow_lean == flow_lean == "counter":
        return schemas.Corroboration(
            category="corroborating",
            summary="Snowpack and streamflow both run counter to a warming signal over the shared record — they corroborate (in the opposite direction).",
            details=details,
        )
    return schemas.Corroboration(
        category="mixed",
        summary="Snowpack and streamflow disagree over the shared record — one leans warming, the other does not.",
        details=details,
    )
