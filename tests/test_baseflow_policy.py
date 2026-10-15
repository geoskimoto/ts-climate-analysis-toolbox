"""Tests for the configurable data-quality policy (docs/baseflow_spec.md section 3b).

Written from the spec only. Synthetic seeded data, no network.

Ambiguities in the spec (tests avoid pinning them):
  * Exact number formatting of <pct> and <limit> in the exclusion reason (only
    the counts "<n> of <N> days interpolated", "exceeds" and the limit digits
    are checked).
  * Whether a gap-free series yields an empty dict or zeros for
    n_interpolated_by_wy (only "all values are 0" is checked).
  * Whether "recession_k" is NaN for data-driven reasons; the tests assert it
    is finite with the rule off before using it as a discriminator.
  * Which Oct 31 closes the recession window (the window has 109 days either way).
  * Unknown method kwargs: no locked test fixes the exception type, so omitted.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from climate_core.stats.baseflow import METHODS, water_year_metrics

AREA = 100.0
# Series Oct 1 1998 .. Sep 30 2001: WY1999 (365 d), WY2000 (366 d, leap), WY2001 (365 d).
START, END = "1998-10-01", "2001-09-30"


def _base():
    idx = pd.date_range(START, END, freq="D")
    rng = np.random.default_rng(42)
    doy = idx.dayofyear.to_numpy()
    q = 50.0 + 30.0 * np.sin(2 * np.pi * (doy - 100) / 365.25) + rng.gamma(2.0, 3.0, len(idx))
    return pd.Series(q, index=idx)


def _with_gaps(*gaps):
    """gaps: (start_date, n_days) pairs, set to NaN."""
    s = _base()
    for start, n in gaps:
        i = s.index.get_loc(pd.Timestamp(start))
        s.iloc[i:i + n] = np.nan
    return s


def _run(series, method="eckhardt", **kw):
    if method == "local_minimum":
        kw.setdefault("drainage_area_sqmi", AREA)
    return water_year_metrics(series, method, **kw)


def _row(df, wy):
    return df.loc[df["water_year"] == wy].iloc[0]


# ------------------------------------------------------------------ (1) defaults == v1
@pytest.mark.parametrize("method", METHODS)
def test_explicit_defaults_equal_implicit_defaults(method):
    s = _with_gaps(("1999-02-01", 2), ("1999-05-10", 3), ("2000-03-01", 5), ("2001-04-01", 1))
    d0, r0 = _run(s, method)
    d1, r1 = _run(s, method, max_gap_days=3, max_interp_frac=0.01, min_window_coverage=None)
    pd.testing.assert_frame_equal(d0, d1)
    assert r0 == r1
    assert r0.n_interpolated == 6          # 2 + 3 + 1 (5-day gap splits, not filled)


# ------------------------------------------------------------------ (2) max_gap_days
def test_10_day_gap_split_at_3_and_filled_at_15():
    s = _with_gaps(("2000-01-10", 10))
    d3, r3 = _run(s)
    assert r3.n_interpolated == 0
    assert 2000 not in set(d3["water_year"])
    assert 2000 in r3.excluded_water_years
    d15, r15 = _run(s, max_gap_days=15, max_interp_frac=0.10)
    assert r15.n_interpolated == 10
    assert r15.n_interpolated_by_wy[2000] == 10
    assert 2000 in set(d15["water_year"])          # 10/366 = 2.7% <= 10%


def test_gap_boundary_inclusive_15_filled_16_split():
    d15, r15 = _run(_with_gaps(("2000-01-10", 15)), max_gap_days=15, max_interp_frac=0.10)
    assert r15.n_interpolated == 15
    assert 2000 in set(d15["water_year"])
    d16, r16 = _run(_with_gaps(("2000-01-10", 16)), max_gap_days=15, max_interp_frac=0.10)
    assert r16.n_interpolated == 0
    assert 2000 not in set(d16["water_year"])
    assert 2000 in r16.excluded_water_years


@pytest.mark.parametrize("bad", [0, -1, -3])
def test_max_gap_days_below_one_raises(bad):
    with pytest.raises(ValueError):
        _run(_base(), max_gap_days=bad)


# ------------------------------------------------------------------ (3) max_interp_frac
def test_frac_40_of_365_excluded_36_kept_at_10pct():
    # WY1999 has 365 days. 40/365 = 10.96% > 10% ; 36/365 = 9.86% <= 10%.
    s40 = _with_gaps(("1999-01-05", 15), ("1999-03-05", 15), ("1999-05-05", 10))
    d, r = _run(s40, max_gap_days=15, max_interp_frac=0.10)
    assert 1999 not in set(d["water_year"])
    reason = r.excluded_water_years[1999]
    assert "40 of 365 days interpolated" in reason
    assert "exceeds" in reason and "10" in reason.split("exceeds")[1]
    assert r.n_interpolated_by_wy[1999] == 40

    s36 = _with_gaps(("1999-01-05", 15), ("1999-03-05", 15), ("1999-05-05", 6))
    d, r = _run(s36, max_gap_days=15, max_interp_frac=0.10)
    assert 1999 in set(d["water_year"])
    assert 1999 not in r.excluded_water_years


def test_frac_strictly_greater_boundary_leap_year():
    # WY2000 has 366 days; limit 0.05. 18/366 = 4.92% kept ; 19/366 = 5.19% excluded.
    s18 = _with_gaps(("2000-01-05", 9), ("2000-03-05", 9))
    d, r = _run(s18, max_gap_days=15, max_interp_frac=0.05)
    assert 2000 in set(d["water_year"])
    s19 = _with_gaps(("2000-01-05", 10), ("2000-03-05", 9))
    d, r = _run(s19, max_gap_days=15, max_interp_frac=0.05)
    assert 2000 not in set(d["water_year"])
    assert "19 of 366 days interpolated" in r.excluded_water_years[2000]


@pytest.mark.parametrize("bad", [1.0, 1.5, -0.01, -1.0])
def test_max_interp_frac_out_of_range_raises(bad):
    with pytest.raises(ValueError):
        _run(_base(), max_interp_frac=bad)


def test_max_interp_frac_zero_accepted_and_excludes_any_interpolation():
    d, r = _run(_with_gaps(("1999-01-05", 1)), max_interp_frac=0.0)
    assert 1999 not in set(d["water_year"])
    d, _ = _run(_base(), max_interp_frac=0.0)
    assert len(d) == 3


# ------------------------------------------------------------------ (4) min_window_coverage
KW = dict(max_gap_days=15, max_interp_frac=0.10)


def test_augsep_gap_nans_augsep_only_by_coverage():
    # 15-day gap in Aug-Sep window (61 d): 15/61 = 24.6% interpolated, 75.4% observed.
    s = _with_gaps(("1999-08-10", 15))
    for cov in (None, 0.70):
        d, _ = _run(s, min_window_coverage=cov, **KW)
        assert np.isfinite(_row(d, 1999)["augsep_baseflow_cfs"])
    d, _ = _run(s, min_window_coverage=0.85, **KW)
    row = _row(d, 1999)
    assert np.isnan(row["augsep_baseflow_cfs"])
    assert np.isfinite(row["junjul_baseflow_cfs"])
    for col in ("bfi", "baseflow_af", "baseflow_cot_dowy"):
        assert np.isfinite(row[col])
    assert np.isfinite(_row(d, 2000)["augsep_baseflow_cfs"])      # other years unaffected


def test_junjul_gap_nans_junjul_only():
    s = _with_gaps(("1999-06-10", 15))
    d, _ = _run(s, min_window_coverage=0.85, **KW)
    row = _row(d, 1999)
    assert np.isnan(row["junjul_baseflow_cfs"])
    assert np.isfinite(row["augsep_baseflow_cfs"])
    for col in ("bfi", "baseflow_af", "baseflow_cot_dowy"):
        assert np.isfinite(row[col])


def test_min7_uses_whole_water_year_window():
    # 15 of 365 interpolated -> 95.9% observed over WY1999.
    s = _with_gaps(("1999-08-10", 15))
    d, _ = _run(s, min_window_coverage=0.95, **KW)
    assert np.isfinite(_row(d, 1999)["min7_baseflow_cfs"])
    d, _ = _run(s, min_window_coverage=0.97, **KW)
    assert np.isnan(_row(d, 1999)["min7_baseflow_cfs"])
    assert np.isfinite(_row(d, 1999)["bfi"])


def test_min7_unaffected_by_gap_when_off():
    d, _ = _run(_with_gaps(("1999-08-10", 15)), **KW)
    assert np.isfinite(_row(d, 1999)["min7_baseflow_cfs"])


def test_recession_k_uses_jul15_oct31_window():
    # Gap Aug 10-24 lies in Jul 15 - Oct 31 (109 d): 15/109 -> 86.2% observed.
    s = _with_gaps(("1999-08-10", 15))
    d, _ = _run(s, **KW)
    assert np.isfinite(_row(d, 1999)["recession_k"])               # precondition
    d, _ = _run(s, min_window_coverage=0.80, **KW)
    assert np.isfinite(_row(d, 1999)["recession_k"])
    d, _ = _run(s, min_window_coverage=0.90, **KW)
    assert np.isnan(_row(d, 1999)["recession_k"])
    # A Jun gap is outside the recession window: unaffected.
    d, _ = _run(_with_gaps(("1999-06-10", 15)), min_window_coverage=0.90, **KW)
    assert np.isfinite(_row(d, 1999)["recession_k"])


def test_coverage_one_accepted_and_any_interpolation_in_window_nans():
    d, _ = _run(_base(), min_window_coverage=1.0)
    assert np.isfinite(_row(d, 1999)["augsep_baseflow_cfs"])
    d, _ = _run(_with_gaps(("1999-09-10", 1)), min_window_coverage=1.0, **KW)
    row = _row(d, 1999)
    assert np.isnan(row["augsep_baseflow_cfs"])
    assert np.isfinite(row["junjul_baseflow_cfs"])


@pytest.mark.parametrize("bad", [0.0, -0.1, 1.01, 2.0])
def test_min_window_coverage_out_of_range_raises(bad):
    with pytest.raises(ValueError):
        _run(_base(), min_window_coverage=bad)


# ------------------------------------------------------------------ (5) n_interpolated_by_wy
def test_by_wy_keys_values_and_sum():
    s = _with_gaps(("1999-02-01", 3), ("2001-04-01", 2))
    _, r = _run(s)
    assert r.n_interpolated == 5
    assert r.n_interpolated_by_wy[1999] == 3
    assert r.n_interpolated_by_wy[2001] == 2
    assert all(isinstance(k, int) and isinstance(v, int) for k, v in r.n_interpolated_by_wy.items())
    assert sum(r.n_interpolated_by_wy.values()) == r.n_interpolated


def test_by_wy_includes_excluded_years():
    # 15 days in WY2000 (4.1%) excluded at the default 1% limit, yet still counted.
    s = _with_gaps(("2000-01-10", 15))
    d, r = _run(s, max_gap_days=15)
    assert 2000 not in set(d["water_year"])
    assert 2000 in r.excluded_water_years
    assert r.n_interpolated_by_wy[2000] == 15
    assert r.n_interpolated == 15


def test_by_wy_gap_free_all_zero():
    _, r = _run(_base())
    assert r.n_interpolated == 0
    assert all(v == 0 for v in r.n_interpolated_by_wy.values())


# ------------------------------------------------------------------ (6) no kwarg leakage
def test_policy_params_do_not_leak_into_method_kwargs():
    s = _with_gaps(("1999-02-01", 2))
    base, _ = _run(s, bfi_max=0.5)
    with_policy, _ = _run(s, bfi_max=0.5, max_gap_days=15, max_interp_frac=0.10,
                          min_window_coverage=0.5)
    pd.testing.assert_frame_equal(base, with_policy)
    default, _ = _run(s)
    assert not np.allclose(base["bfi"], default["bfi"])             # bfi_max took effect


@pytest.mark.parametrize("method", ["lyne_hollick", "local_minimum"])
def test_policy_params_accepted_for_other_methods(method):
    d, r = _run(_with_gaps(("1999-02-01", 10)), method, max_gap_days=15, max_interp_frac=0.10,
                min_window_coverage=0.5)
    assert 1999 in set(d["water_year"]) and r.n_interpolated == 10
