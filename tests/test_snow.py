"""Snow (SNOTEL) pipeline tests — synthetic (offline) plus catalog + live."""

import pytest

from climate_core import DataLoader, NRCSSnotel, Snow, mk_to_dict
from climate_core.catalog import default_snotel_catalog


def _build(synthetic_swe):
    return Snow(DataLoader(synthetic_swe, date_column="Date", value_column="WTEQ"))


def test_peak_swe_detects_engineered_decline(synthetic_swe):
    s = _build(synthetic_swe)
    s.calc_max(window_size=1, alpha=0.05)
    mag = mk_to_dict(s.rolling_yr_Qmax_mk_test)
    assert mag["trend"] == "decreasing"
    assert mag["significant"] is True
    assert mag["slope"] < 0
    assert len(s.rolling_yr_maxs) == s._df["Water Year"].nunique()


def test_benchmark_swe_series(synthetic_swe):
    s = _build(synthetic_swe)
    s.calc_benchmark_swe("04-01", alpha=0.05)
    # One April-1 value per water year, and the engineered decline shows.
    assert len(s.benchmark_swe_df) == s._df["Water Year"].nunique()
    assert mk_to_dict(s.benchmark_swe_mann_kendall_test)["trend"] == "decreasing"


def test_melt_out_date_detected(synthetic_swe):
    s = _build(synthetic_swe)
    s.calc_melt_out_date(alpha=0.05)
    # Melt-out engineered near day 240 of the water year.
    assert (s.melt_out_df["dayofwateryear"].between(220, 260)).all()
    assert mk_to_dict(s.melt_out_mann_kendall_test)["trend"] in {"increasing", "decreasing", "no trend"}


def test_melt_out_skips_snow_free_years(synthetic_swe):
    s = _build(synthetic_swe)
    s.calc_melt_out_date(min_peak=1000.0)  # nothing exceeds this -> all years skipped
    assert s.melt_out_df.empty


# --- catalog ---------------------------------------------------------------- #
def test_snotel_catalog_loads_and_geocoded():
    cat = default_snotel_catalog()
    assert len(cat) > 400
    for st in cat.all():
        assert st.lat is not None and st.long is not None
        assert 40 <= st.lat <= 50
        assert st.huc  # HUC present -> future basin pairing possible


def test_snotel_catalog_get_and_search():
    cat = default_snotel_catalog()
    st = cat.get("302:OR:SNTL")
    assert "ANEROID" in st.name.upper()
    assert cat.search(state="MT")
    with pytest.raises(KeyError):
        cat.get("999999:ZZ:SNTL")


def test_snotel_by_huc_prefix():
    cat = default_snotel_catalog()
    # HUC-17 = Pacific Northwest region.
    assert cat.by_huc("17")


# --- live ------------------------------------------------------------------- #
@pytest.mark.network
def test_snotel_fetch_and_pipeline():
    raw = NRCSSnotel().get_data(
        begin_date="1980-10-01", end_date="2020-09-30",
        station_triplets="302:OR:SNTL", elements=["WTEQ"],
    )
    assert "WTEQ" in raw.columns and len(raw) > 5000
    s = Snow(DataLoader(raw, "Date", "WTEQ"))
    s.calc_benchmark_swe("04-01")
    assert mk_to_dict(s.benchmark_swe_mann_kendall_test)["trend"] in {
        "increasing", "decreasing", "no trend",
    }
