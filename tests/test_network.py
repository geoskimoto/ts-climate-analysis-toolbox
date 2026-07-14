"""Live data-source tests. Marked 'network' -- run with: pytest -m network"""

import pytest

from climate_core import DataLoader, Streamflow, USGSStreamflow, mk_to_dict

pytestmark = pytest.mark.network


def test_usgs_fetch_and_full_pipeline():
    raw = USGSStreamflow().get_data(
        sites="13340000",  # Clearwater R at Orofino
        start_date="1960-10-01",
        end_date="2020-09-30",
    )
    assert list(raw.columns) == ["Date", "Discharge"]
    assert len(raw) > 10_000

    loader = DataLoader(raw, date_column="Date", value_column="Discharge")
    s = Streamflow(loader)
    s.calc_annual_runoff_threshold_day(percent=0.5, alpha=0.10)

    result = mk_to_dict(s.threshold_vol_dates_mann_kendall_test)
    assert result["trend"] in {"increasing", "decreasing", "no trend"}
    assert 0.0 <= result["p_value"] <= 1.0


def test_usgs_bad_site_raises():
    with pytest.raises((ValueError, Exception)):
        USGSStreamflow().get_data(sites="00000000", start_date="2020-01-01", end_date="2020-02-01")
