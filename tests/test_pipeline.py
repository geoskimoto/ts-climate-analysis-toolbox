"""End-to-end pipeline tests on synthetic data (no network)."""

import pandas as pd

from climate_core import DataLoader, Streamflow, mk_to_dict


def _build(synthetic_streamflow):
    loader = DataLoader(synthetic_streamflow, date_column="Date", value_column="Discharge")
    return Streamflow(loader)


def test_water_year_columns_added(synthetic_streamflow):
    s = _build(synthetic_streamflow)
    for col in ["WY_Date", "Water Year", "Calendar Year", "month-day", "dayofyear"]:
        assert col in s._df.columns
    # Oct-Dec dates are shifted forward into the following (labelled) water year.
    oct_row = s._df[s._df["Date"] == pd.Timestamp("1970-10-15")].iloc[0]
    assert oct_row["Water Year"] == 1971


def test_climatology_envelope_shape(synthetic_streamflow):
    s = _build(synthetic_streamflow)
    # One row per calendar day-of-year (365/366), ordered water-year style.
    assert 365 <= len(s._stats) <= 366
    assert s._stats.iloc[0]["month-day"].startswith("10")  # water year starts in October
    assert (s._upper_bound_st_dev >= s._lower_bound_st_dev).all()


def test_center_of_timing_detects_engineered_trend(synthetic_streamflow):
    s = _build(synthetic_streamflow)
    s.calc_annual_runoff_threshold_day(percent=0.5, alpha=0.05)

    result = mk_to_dict(s.threshold_vol_dates_mann_kendall_test)
    # We engineered the peak to drift earlier -> day-of-year should trend down.
    assert result["trend"] == "decreasing"
    assert result["significant"] is True
    assert result["slope"] < 0
    # One threshold date per water year.
    assert len(s.threshold_vol_stats) == s._df["Water Year"].nunique()


def test_seasonal_volume_runs(synthetic_streamflow):
    s = _build(synthetic_streamflow)
    s.calc_runoff_bw_days(begin_month_day="04-01", end_month_day="06-30", alpha=0.05)
    assert len(s.volume_bw_days_df) == s._df["Water Year"].nunique()
    assert (s.volume_bw_days_df["Discharge"] >= 0).all()


def test_peak_timing_runs(synthetic_streamflow):
    s = _build(synthetic_streamflow)
    s.calc_max(window_size=7, alpha=0.05)
    assert len(s.rolling_yr_maxs) == s._df["Water Year"].nunique()
    doy_trend = mk_to_dict(s.rolling_yr_DOYmax_mk_test)
    assert doy_trend["trend"] in {"increasing", "decreasing", "no trend"}


def test_ignore_winter_months_restricts_search(synthetic_streamflow):
    s = _build(synthetic_streamflow)
    s.calc_max(window_size=7, ignore_winter_months=True)
    assert (s.rolling_yr_maxs["month-day"] >= "02-01").all()
    assert (s.rolling_yr_maxs["month-day"] <= "07-01").all()


def test_mk_to_dict_is_json_serialisable(synthetic_streamflow):
    import json

    s = _build(synthetic_streamflow)
    s.calc_annual_runoff_threshold_day(percent=0.5)
    payload = mk_to_dict(s.total_volume_mann_kendall_test)
    json.dumps(payload)  # must not raise
    assert set(payload) >= {"trend", "significant", "p_value", "slope"}
