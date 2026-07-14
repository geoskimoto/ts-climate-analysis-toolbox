"""Shared fixtures: synthetic streamflow with a built-in warming signal."""

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def synthetic_streamflow():
    """A daily discharge series (water years 1951-2020) whose snowmelt peak
    drifts *earlier* each year -- i.e. an engineered center-of-timing trend the
    Mann-Kendall test should flag as 'decreasing' day-of-year.

    Deterministic (seeded) so trend assertions are stable.
    """
    rng = np.random.default_rng(42)
    start = pd.Timestamp("1950-10-01")
    end = pd.Timestamp("2020-09-30")
    dates = pd.date_range(start, end, freq="D")

    records = []
    for d in dates:
        water_year = d.year + 1 if d.month >= 10 else d.year
        years_elapsed = water_year - 1951
        # Peak day-of-water-year drifts ~0.5 day earlier per year (warming).
        peak_doy = 210 - 0.5 * years_elapsed
        wy_doy = (d - pd.Timestamp(f"{water_year - 1}-10-01")).days
        base = 200.0 * np.exp(-((wy_doy - peak_doy) ** 2) / (2 * 45.0 ** 2))
        discharge = max(1.0, base + rng.normal(0, 5))
        records.append({"Date": d.date(), "Discharge": round(discharge, 2)})

    return pd.DataFrame(records)


@pytest.fixture
def synthetic_swe():
    """Daily SWE (water years 1985-2020) as an accumulate-then-melt sawtooth
    whose peak magnitude *declines* ~0.3 in/year — an engineered snowpack-loss
    signal the Mann-Kendall test should flag as 'decreasing' peak SWE. Melt-out
    (SWE returns to 0) lands ~day 240 of the water year.
    """
    import numpy as np

    rng = np.random.default_rng(7)
    dates = pd.date_range(pd.Timestamp("1984-10-01"), pd.Timestamp("2020-09-30"), freq="D")
    peak_day = 150  # ~1 March in day-of-water-year terms

    records = []
    for d in dates:
        water_year = d.year + 1 if d.month >= 10 else d.year
        dowy = (d - pd.Timestamp(year=water_year - 1, month=10, day=1)).days + 1
        peak_mag = max(2.0, 30.0 - 0.3 * (water_year - 1985))
        if dowy < peak_day:
            swe = peak_mag * (dowy / peak_day)
        else:
            swe = max(0.0, peak_mag * (1 - (dowy - peak_day) / 90.0))
        swe = max(0.0, swe + rng.normal(0, 0.3))
        records.append({"Date": d.date(), "WTEQ": round(swe, 2)})

    return pd.DataFrame(records)
