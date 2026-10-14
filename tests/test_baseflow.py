"""Tests for ``climate_core.stats.baseflow`` written from docs/baseflow_spec.md.

Synthetic data only, fixed seeds, no network. Expected values are derived by
hand or from analytic generators -- the separation filters are NOT
re-implemented here. Section numbers in class docstrings refer to the spec.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pymannkendall as pmk
import pytest

from api.common import day_of_water_year
from climate_core.stats.baseflow import (
    METHODS,
    QualityReport,
    baseflow_trends,
    eckhardt,
    local_minimum,
    lyne_hollick,
    method_range,
    water_year_metrics,
)
from climate_core.stats.mk import mk_to_dict

AF_PER_CFS_DAY = 1.9835
AREA_SQMI = 100.0  # 2N = 4.02 -> 2N* = 5 (window of 5 days)
METRIC_COLS = [
    "water_year",
    "bfi",
    "baseflow_af",
    "junjul_baseflow_cfs",
    "augsep_baseflow_cfs",
    "min7_baseflow_cfs",
    "baseflow_cot_dowy",
    "recession_k",
]
TREND_METRICS = METRIC_COLS[1:]


# --------------------------------------------------------------------------- helpers
def _sep(method: str, q: np.ndarray) -> np.ndarray:
    if method == "lyne_hollick":
        return lyne_hollick(q)
    if method == "eckhardt":
        return eckhardt(q)
    return local_minimum(q, AREA_SQMI)


def _wy_of(index: pd.DatetimeIndex) -> np.ndarray:
    return np.where(index.month >= 10, index.year + 1, index.year)


def _daily(start: str, end: str, values) -> pd.Series:
    idx = pd.date_range(start, end, freq="D")
    if np.isscalar(values):
        arr = np.full(len(idx), float(values))
    else:
        arr = np.asarray(values, dtype=float)
    return pd.Series(arr, index=idx)


def _metrics(series, method, **kw):
    if method == "local_minimum":
        kw.setdefault("drainage_area_sqmi", AREA_SQMI)
    return water_year_metrics(series, method, **kw)


def _synthetic_hydrograph(n_years: int = 5, seed: int = 11):
    """Known baseflow (slow rise then exponential recession, k=0.985/day) plus
    exponentially decaying (0.6/day) storm pulses. Returns (series, base)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("1995-10-01", periods=0, freq="D")
    idx = pd.date_range("1995-10-01", f"{1995 + n_years}-09-30", freq="D")
    wy = _wy_of(idx)
    dowy = np.array([(d - pd.Timestamp(year=w - 1, month=10, day=1)).days for d, w in zip(idx, wy)])
    base = np.where(
        dowy < 90,
        31.0 + (100.0 - 31.0) * dowy / 90.0,
        30.0 + 70.0 * 0.985 ** (dowy - 90),
    )
    quick = np.zeros(len(idx))
    day = 15
    while day < len(idx) - 40:
        amp = rng.uniform(20.0, 100.0)
        n = len(idx) - day
        quick[day:] += amp * 0.6 ** np.arange(n)
        day += int(rng.integers(10, 22))
    return pd.Series(base + quick, index=idx), base


# =========================================================================== API / sec 7a
class TestPublicApi:
    def test_methods_constant(self):
        assert tuple(METHODS) == ("lyne_hollick", "eckhardt", "local_minimum")

    def test_quality_report_fields(self):
        qr = QualityReport(n_interpolated=0, skipped_runs=[], excluded_water_years={})
        assert qr.n_interpolated == 0
        assert qr.skipped_runs == []
        assert qr.excluded_water_years == {}

    def test_metrics_return_shape_and_columns(self):
        s = _daily("1995-10-01", "1997-09-30", 10.0)
        df, qr = water_year_metrics(s, "lyne_hollick")
        assert isinstance(df, pd.DataFrame)
        assert isinstance(qr, QualityReport)
        assert list(df.columns) == METRIC_COLS
        assert isinstance(df.index, pd.RangeIndex)
        assert df["water_year"].tolist() == [1996, 1997]
        assert np.issubdtype(df["water_year"].dtype, np.integer)

    def test_default_arguments(self):
        # Default-argument calls must work as per the signatures.
        q = np.full(60, 5.0)
        assert len(lyne_hollick(q)) == 60
        assert len(eckhardt(q)) == 60
        assert len(local_minimum(q, 50.0)) == 60


# =========================================================================== shared invariants
@pytest.mark.parametrize("method", METHODS)
class TestSharedInvariants:
    def _storm_q(self):
        s, _ = _synthetic_hydrograph(n_years=2)
        return s.to_numpy().copy()

    def test_bounds_length_finite(self, method):
        q = self._storm_q()
        b = _sep(method, q)
        assert isinstance(b, np.ndarray)
        assert b.shape == q.shape
        assert np.all(np.isfinite(b))
        assert np.all(b >= 0.0)
        assert np.all(b <= q + 1e-9)

    def test_bounds_with_zeros_and_spikes(self, method):
        rng = np.random.default_rng(3)
        q = rng.gamma(0.5, 10.0, size=400)
        q[::17] = 0.0
        q[200] = 5000.0
        b = _sep(method, q)
        assert len(b) == len(q)
        assert np.all(np.isfinite(b))
        assert np.all(b >= 0.0)
        assert np.all(b <= q + 1e-9)

    def test_input_not_mutated(self, method):
        q = self._storm_q()
        before = q.copy()
        _sep(method, q)
        np.testing.assert_array_equal(q, before)

    def test_ends_finite_and_bounded(self, method):
        q = self._storm_q()
        b = _sep(method, q)
        for sl in (slice(0, 30), slice(-30, None)):
            assert not np.isnan(b[sl]).any()
            assert np.all(b[sl] <= q[sl] + 1e-9)
            assert np.all(b[sl] >= 0.0)

    def test_series_input_not_mutated_by_metrics(self, method):
        s, _ = _synthetic_hydrograph(n_years=3)
        before = s.copy()
        _metrics(s, method)
        pd.testing.assert_series_equal(s, before)

    def test_metrics_no_nan_in_core_columns(self, method):
        s, _ = _synthetic_hydrograph(n_years=3)
        df, _ = _metrics(s, method)
        assert len(df) >= 1
        core = ["bfi", "baseflow_af", "junjul_baseflow_cfs", "augsep_baseflow_cfs",
                "min7_baseflow_cfs", "baseflow_cot_dowy"]
        assert not df[core].isna().any().any()
        assert df["bfi"].between(0.0, 1.0).all()


# =========================================================================== sec 4 / 9 constant
class TestConstantDischarge:
    """Sec 9: constant discharge -> b == q, bfi == 1.

    NOTE: Eckhardt is excluded -- spec 4.2 (b[0]=bfi_max*q[0]) contradicts this
    property; see TestEckhardt for the literal 4.2 behaviour.
    """

    @pytest.mark.parametrize("method", ["lyne_hollick", "local_minimum"])
    @pytest.mark.parametrize("level", [0.0, 0.5, 10.0, 12345.6])
    def test_b_equals_q(self, method, level):
        q = np.full(500, level)
        np.testing.assert_allclose(_sep(method, q), q, rtol=1e-9, atol=1e-12)

    @pytest.mark.parametrize("method", ["lyne_hollick", "local_minimum"])
    def test_bfi_one(self, method):
        s = _daily("1995-10-01", "1998-09-30", 10.0)
        df, _ = _metrics(s, method)
        assert len(df) == 3
        np.testing.assert_allclose(df["bfi"], 1.0, atol=1e-9)


# =========================================================================== sec 4.1
class TestLyneHollick:
    def test_single_pass_spike_hand_value(self):
        # Constant 10 with a one-day spike to 15: qf[spike] = (1+0.925)/2 * 5,
        # qf is then clipped to 0 on the falling day. Ends are constant so the
        # reflection does not change anything.
        q = np.full(101, 10.0)
        q[50] = 15.0
        b = lyne_hollick(q, alpha=0.925, passes=1)
        expected = np.full(101, 10.0)
        expected[50] = 15.0 - (1.925 / 2.0) * 5.0
        np.testing.assert_allclose(b, expected, atol=1e-9)

    def test_three_pass_spike_between_background_and_one_pass(self):
        q = np.full(101, 10.0)
        q[50] = 15.0
        b = lyne_hollick(q)  # defaults: alpha=0.925, passes=3
        assert 10.0 - 1e-9 <= b[50] <= 15.0 - (1.925 / 2.0) * 5.0 + 1e-9
        np.testing.assert_allclose(np.delete(b, 50), 10.0, atol=1e-6)

    @pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.5])
    def test_alpha_validation(self, alpha):
        with pytest.raises(ValueError):
            lyne_hollick(np.full(100, 5.0), alpha=alpha)

    def test_ends_of_flat_series_unchanged_after_trim(self):
        q = np.full(200, 7.0)
        q[100] = 30.0
        b = lyne_hollick(q)
        assert len(b) == 200
        np.testing.assert_allclose(b[:30], 7.0, atol=1e-9)
        np.testing.assert_allclose(b[-30:], 7.0, atol=1e-9)


# =========================================================================== sec 4.2
class TestEckhardt:
    def test_initial_value_and_hand_steps(self):
        # alpha=0.98, bfi_max=0.8 => denominator 1 - 0.784 = 0.216
        # b0 = min(q0, 0.8*q0) = 8
        # q=10 -> b stays 8 (fixed point); spike q=15:
        # b = (0.2*0.98*8 + 0.02*0.8*15) / 0.216
        q = np.array([10.0, 10.0, 10.0, 10.0, 10.0, 15.0, 10.0])
        b = eckhardt(q)
        assert b[0] == pytest.approx(8.0)
        np.testing.assert_allclose(b[:5], 8.0, atol=1e-9)
        assert b[5] == pytest.approx((0.196 * 8.0 + 0.016 * 15.0) / 0.216)

    def test_min_with_q_clipping(self):
        # Unclipped b1 would be (0.196*8 + 0.016*1)/0.216 = 7.33 > q1=1.
        b = eckhardt(np.array([10.0, 1.0]))
        np.testing.assert_allclose(b, [8.0, 1.0], atol=1e-9)

    def test_rising_step_hand_value(self):
        b = eckhardt(np.array([10.0, 20.0]))
        assert b[1] == pytest.approx((0.196 * 8.0 + 0.016 * 20.0) / 0.216)

    def test_custom_bfi_max_constant_series(self):
        # bfi_max=0.5: b0 = 5; b1 = (0.5*0.98*5 + 0.02*0.5*10)/(1-0.49) = 5.
        b = eckhardt(np.full(50, 10.0), bfi_max=0.5)
        np.testing.assert_allclose(b, 5.0, atol=1e-9)

    @pytest.mark.parametrize("bfi_max", [0.0, 1.0, -0.1, 1.5])
    def test_bfi_max_validation(self, bfi_max):
        with pytest.raises(ValueError):
            eckhardt(np.full(50, 10.0), bfi_max=bfi_max)

    @pytest.mark.parametrize("alpha", [0.0, 1.0, -0.1, 1.5])
    def test_alpha_validation(self, alpha):
        with pytest.raises(ValueError):
            eckhardt(np.full(50, 10.0), alpha=alpha)

    def test_metrics_kwargs_passthrough(self):
        s = _daily("1995-10-01", "1997-09-30", 10.0)
        df, _ = water_year_metrics(s, "eckhardt", bfi_max=0.5)
        np.testing.assert_allclose(df["bfi"], 0.5, atol=1e-9)


# =========================================================================== sec 4.3
class TestLocalMinimum:
    Q_SMALL = np.array([10.0, 9.0, 5.0, 6.0, 4.0, 7.0, 8.0, 9.0, 12.0])

    def test_window3_hand_value(self):
        # A=1 -> 2N=1.6 -> nearest odd 1 -> clipped to 3. Minima: idx2 (5), idx4 (4).
        b = local_minimum(self.Q_SMALL, 1.0)
        np.testing.assert_allclose(b, [5, 5, 5, 4.5, 4, 4, 4, 4, 4], atol=1e-9)

    def test_lower_clip_is_three(self):
        np.testing.assert_allclose(
            local_minimum(self.Q_SMALL, 0.001), local_minimum(self.Q_SMALL, 1.0)
        )

    def test_window5_hand_value(self):
        # A=300 -> 2N = 5.006 -> 5. idx2 is no longer a minimum (idx4 within window).
        b = local_minimum(self.Q_SMALL, 300.0)
        np.testing.assert_allclose(b, 4.0, atol=1e-9)

    @staticmethod
    def _ramp(dip_idx):
        i = np.arange(31)
        q = 20.0 + 0.1 * np.abs(i - 15)
        q[15] = 1.0
        q[dip_idx] = 5.0
        return q

    def test_window9(self):
        # A=5600 -> 2N = 8.99 -> 9: idx10 (+-4 -> 6..14) excludes the deep min at 15.
        b = local_minimum(self._ramp(10), 5600.0)
        assert b[0] == pytest.approx(5.0)
        assert b[-1] == pytest.approx(1.0)

    def test_upper_clip_is_eleven_not_smaller(self):
        # A huge -> clipped to 11 (+-5): idx10 window 5..15 contains the deep min.
        b = local_minimum(self._ramp(10), 1e9)
        assert b[0] == pytest.approx(1.0)

    def test_upper_clip_is_eleven_not_larger(self):
        # idx9 window (+-5) is 4..14, excludes 15 -> idx9 is a minimum. A window
        # of 13 (+-6) would include idx15 and remove it.
        b = local_minimum(self._ramp(9), 1e9)
        assert b[0] == pytest.approx(5.0)
        assert b[-1] == pytest.approx(1.0)

    def test_step_series_interpolates_between_minima(self):
        # Plateaus 20 (30 days), 10 (30 days), 20 (30 days), window 3.
        # Step down at idx30: idx29 not a min, idx28 is (20), idx30 is (10) -> b[29]=15.
        # Step up at idx60: idx59 min (10), idx60 not, idx61 min (20) -> b[60]=15.
        q = np.concatenate([np.full(30, 20.0), np.full(30, 10.0), np.full(30, 20.0)])
        b = local_minimum(q, 1.0)
        assert b[29] == pytest.approx(15.0)
        assert b[60] == pytest.approx(15.0)
        np.testing.assert_allclose(b[:29], 20.0)
        np.testing.assert_allclose(b[30:60], 10.0)
        np.testing.assert_allclose(b[61:], 20.0)

    def test_metrics_requires_area(self):
        s = _daily("1995-10-01", "1997-09-30", 10.0)
        with pytest.raises(ValueError):
            water_year_metrics(s, "local_minimum")
        with pytest.raises(ValueError):
            water_year_metrics(s, "local_minimum", drainage_area_sqmi=None)


# =========================================================================== sec 9 known-truth
class TestSyntheticTruth:
    """Known baseflow + injected storms: BFI within spec tolerance of truth."""

    @pytest.mark.parametrize(
        "method, tol",
        [("lyne_hollick", 0.10), ("eckhardt", 0.10), ("local_minimum", 0.15)],
    )
    def test_bfi_close_to_truth(self, method, tol):
        s, base = _synthetic_hydrograph(n_years=5)
        q = s.to_numpy().copy()
        truth = base.sum() / q.sum()
        b = _sep(method, q)
        assert np.all(b >= 0) and np.all(b <= q + 1e-9)
        assert abs(b.sum() / q.sum() - truth) <= tol

    @pytest.mark.parametrize(
        "method, tol",
        [("lyne_hollick", 0.10), ("eckhardt", 0.10), ("local_minimum", 0.15)],
    )
    def test_metrics_bfi_close_to_truth_per_wy(self, method, tol):
        s, base = _synthetic_hydrograph(n_years=5)
        df, _ = _metrics(s, method)
        wy = _wy_of(s.index)
        assert len(df) == 5
        for _, row in df.iterrows():
            m = wy == int(row["water_year"])
            truth = base[m].sum() / s.to_numpy()[m].sum()
            assert abs(row["bfi"] - truth) <= tol


# =========================================================================== sec 3
@pytest.mark.parametrize("method", METHODS)
class TestGapPolicy:
    def test_three_day_gap_interpolated_and_counted(self, method):
        s = _daily("1995-10-01", "1998-09-30", 10.0)
        s.loc["1996-12-10":"1996-12-12"] = np.nan
        df, qr = _metrics(s, method)
        assert qr.n_interpolated == 3
        assert qr.skipped_runs == []
        assert qr.excluded_water_years == {}
        assert df["water_year"].tolist() == [1996, 1997, 1998]

    def test_three_day_gap_filled_not_zeroed(self, method):
        if method == "eckhardt":
            pytest.skip("constant-series BFI for Eckhardt is bfi_max (spec 4.2)")
        s = _daily("1995-10-01", "1998-09-30", 10.0)
        s.loc["1996-12-10":"1996-12-12"] = np.nan
        df, _ = _metrics(s, method)
        np.testing.assert_allclose(df["bfi"], 1.0, atol=1e-9)

    def test_negative_discharge_is_missing(self, method):
        s = _daily("1995-10-01", "1998-09-30", 10.0)
        s.loc["1997-03-01":"1997-03-02"] = -9999.0
        df, qr = _metrics(s, method)
        assert qr.n_interpolated == 2
        assert 1997 in df["water_year"].tolist()
        if method != "eckhardt":
            np.testing.assert_allclose(df["bfi"], 1.0, atol=1e-9)

    def test_zero_is_valid_not_interpolated(self, method):
        s = _daily("1995-10-01", "1998-09-30", 10.0)
        s.loc["1997-03-01"] = 0.0
        s.loc["1997-03-10"] = 0.0
        df, qr = _metrics(s, method)
        assert qr.n_interpolated == 0
        assert qr.excluded_water_years == {}

    def test_four_day_gap_splits_run(self, method):
        s = _daily("1995-10-01", "2000-09-30", 10.0)
        s.loc["1997-01-10":"1997-01-13"] = np.nan  # 4 consecutive days
        df, qr = _metrics(s, method)
        assert qr.n_interpolated == 0
        assert qr.skipped_runs == []  # both runs are >= 365 days
        assert 1997 in qr.excluded_water_years
        assert isinstance(qr.excluded_water_years[1997], str)
        assert qr.excluded_water_years[1997] != ""
        assert df["water_year"].tolist() == [1996, 1998, 1999, 2000]

    def test_short_run_reported_as_skipped(self, method):
        s = _daily("1995-10-01", "1998-09-30", 10.0)
        s.loc["1996-01-09":"1996-01-12"] = np.nan  # leaves a 100-day first run
        df, qr = _metrics(s, method)
        assert len(qr.skipped_runs) == 1
        start, end = qr.skipped_runs[0]
        assert pd.Timestamp(start) == pd.Timestamp("1995-10-01")
        assert pd.Timestamp(end) > pd.Timestamp(start)
        assert 1996 in qr.excluded_water_years
        assert 1996 not in df["water_year"].tolist()
        assert df["water_year"].tolist() == [1997, 1998]

    def test_more_than_one_percent_interpolated_excluded(self, method):
        s = _daily("1995-10-01", "1998-09-30", 10.0)
        # 6 interpolated days in WY1997 (6/365 = 1.6% > 1%), two separate 3-day gaps.
        s.loc["1997-01-10":"1997-01-12"] = np.nan
        s.loc["1997-04-10":"1997-04-12"] = np.nan
        df, qr = _metrics(s, method)
        assert qr.n_interpolated == 6
        assert 1997 in qr.excluded_water_years
        assert qr.excluded_water_years[1997]  # non-empty reason
        assert df["water_year"].tolist() == [1996, 1998]
        assert qr.skipped_runs == []

    def test_duplicate_dates_raise(self, method):
        s = _daily("1995-10-01", "1997-09-30", 10.0)
        dup = pd.concat([s, s.iloc[[5]]]).sort_index()
        with pytest.raises(ValueError):
            _metrics(dup, method)


class TestWaterYearCompleteness:
    def test_partial_boundary_years_excluded_and_listed(self):
        # 1995-09-30 is the last day of WY1995; 1997-10-01 is the first day of WY1998.
        s = _daily("1995-09-30", "1997-10-01", 10.0)
        df, qr = water_year_metrics(s, "lyne_hollick")
        assert df["water_year"].tolist() == [1996, 1997]
        assert set(qr.excluded_water_years) == {1995, 1998}
        assert all(isinstance(v, str) and v for v in qr.excluded_water_years.values())

    def test_oct_1_labels_next_water_year(self):
        s = _daily("1995-10-01", "1996-09-30", 10.0)
        df, _ = water_year_metrics(s, "lyne_hollick")
        assert df["water_year"].tolist() == [1996]

    def test_exactly_one_percent_interpolation_not_excluded(self):
        # 3 days / 365 = 0.82% <= 1%
        s = _daily("1995-10-01", "1998-09-30", 10.0)
        s.loc["1997-06-01":"1997-06-03"] = np.nan
        df, qr = water_year_metrics(s, "lyne_hollick")
        assert 1997 in df["water_year"].tolist()
        assert 1997 not in qr.excluded_water_years

    def test_day_of_water_year_reference(self):
        # Reference helper the spec points to for DOWY.
        assert day_of_water_year(pd.Timestamp("1998-10-01"), 1999) == 1
        assert day_of_water_year(pd.Timestamp("1999-09-30"), 1999) == 365
        assert day_of_water_year(pd.Timestamp("2000-09-30"), 2000) == 366
        assert day_of_water_year(pd.Timestamp("2000-03-01"), 2000) == 153
        assert day_of_water_year(pd.Timestamp("1999-03-01"), 1999) == 152


# =========================================================================== sec 5 metrics
def _profile_series(start: str, end: str) -> pd.Series:
    """Plateau hydrograph: 50 cfs Oct 1-May 31, 30 cfs Jun 1-Jul 31, 10 cfs Aug 1-Sep 30."""
    idx = pd.date_range(start, end, freq="D")
    md = idx.month * 100 + idx.day
    q = np.where(md >= 801, 10.0, np.where(md >= 601, 30.0, 50.0))
    q = np.where((md >= 1001), 50.0, q)
    return pd.Series(q, index=idx)


def _expected_b_profile(n_hi: int) -> np.ndarray:
    """Hand-derived local-minimum (window 3) baseflow for one interior WY of the
    plateau series. Local minima: every plateau day except the day before a
    step-down and the day of a step-up; linear interpolation across those.
      Oct 1 (step up 10->50)   : (10+50)/2 = 30
      May 31 (day before 50->30): (50+30)/2 = 40
      Jul 31 (day before 30->10): (30+10)/2 = 20
    """
    b = np.concatenate([np.full(n_hi, 50.0), np.full(61, 30.0), np.full(61, 10.0)])
    b[0] = 30.0
    b[n_hi - 1] = 40.0
    b[n_hi + 61 - 1] = 20.0
    return b


class TestMetricDefinitions:
    """Local-minimum (A=1 -> window 3) on a plateau series is hand-computable."""

    @pytest.mark.parametrize(
        "start, end, wy, n_hi",
        [
            ("1995-10-01", "1999-09-30", 1997, 243),  # non-leap WY
            ("1995-10-01", "1999-09-30", 1998, 243),
            ("1998-10-01", "2001-09-30", 2000, 244),  # leap WY (Feb 29, 2000)
        ],
    )
    def test_plateau_metrics(self, start, end, wy, n_hi):
        s = _profile_series(start, end)
        df, _ = water_year_metrics(s, "local_minimum", drainage_area_sqmi=1.0)
        row = df[df["water_year"] == wy].iloc[0]

        b = _expected_b_profile(n_hi)
        q = np.concatenate([np.full(n_hi, 50.0), np.full(61, 30.0), np.full(61, 10.0)])
        assert len(b) == (366 if n_hi == 244 else 365)

        assert row["bfi"] == pytest.approx(b.sum() / q.sum())
        assert row["baseflow_af"] == pytest.approx(b.sum() * AF_PER_CFS_DAY)
        # Jun 1 - Jul 31 = 61 days starting at index n_hi
        assert row["junjul_baseflow_cfs"] == pytest.approx(b[n_hi:n_hi + 61].mean())
        assert row["augsep_baseflow_cfs"] == pytest.approx(10.0)
        assert row["min7_baseflow_cfs"] == pytest.approx(10.0)
        cot = int(np.argmax(np.cumsum(b) >= 0.5 * b.sum())) + 1  # DOWY, Oct 1 = 1
        assert row["baseflow_cot_dowy"] == cot
        assert np.isnan(row["recession_k"])  # only 2 declining days (< 10)

    def test_baseflow_af_consistent_with_bfi_and_input(self):
        s, _ = _synthetic_hydrograph(n_years=3)
        for method in METHODS:
            df, _ = _metrics(s, method)
            wy = _wy_of(s.index)
            for _, row in df.iterrows():
                sum_q = s.to_numpy()[wy == int(row["water_year"])].sum()
                assert row["baseflow_af"] == pytest.approx(
                    row["bfi"] * sum_q * AF_PER_CFS_DAY, rel=1e-9
                )

    def test_constant_series_metrics_leap_and_nonleap(self):
        # lyne_hollick on constant 10 cfs => b == q.
        s = _daily("1998-10-01", "2001-09-30", 10.0)
        df, _ = water_year_metrics(s, "lyne_hollick")
        by_wy = df.set_index("water_year")
        assert by_wy.loc[1999, "baseflow_af"] == pytest.approx(10.0 * 365 * AF_PER_CFS_DAY)
        assert by_wy.loc[2000, "baseflow_af"] == pytest.approx(10.0 * 366 * AF_PER_CFS_DAY)
        assert by_wy.loc[2001, "baseflow_af"] == pytest.approx(10.0 * 365 * AF_PER_CFS_DAY)
        # cumulative 10*d >= 0.5*total: first d = 183 for both 365 and 366 days
        assert (df["baseflow_cot_dowy"] == 183).all()
        np.testing.assert_allclose(df["junjul_baseflow_cfs"], 10.0)
        np.testing.assert_allclose(df["augsep_baseflow_cfs"], 10.0)
        np.testing.assert_allclose(df["min7_baseflow_cfs"], 10.0)
        assert df["recession_k"].isna().all()

    def test_recession_k_median_of_declining_day_ratios(self):
        # Interior WY1997 of a staircase: 100 cfs until Jul 14, then 10-day
        # plateaus each 0.8x the previous one (Jul 15 onward). With window 3:
        #   day before each step-down: b = (H+L)/2 = 0.9 H    -> ratio 0.9
        #   first day of lower plateau: b = L = 0.8 H           -> ratio 0.8/0.9
        # Declining days in Jul 15 - Oct 31: Jul 15 (0.8/0.9) plus 7 steps
        # (Jul 25, Aug 4, 14, 24, Sep 3, 13, 23) each giving one 0.9 and one 0.8/0.9
        # => 8 x (8/9) and 7 x 0.9; median (8th of 15) = 8/9.
        idx = pd.date_range("1995-10-01", "1999-09-30", freq="D")
        wy = _wy_of(idx)
        q = np.empty(len(idx))
        for i, (d, w) in enumerate(zip(idx, wy)):
            jul15 = pd.Timestamp(year=w, month=7, day=15)
            k = (d - jul15).days
            q[i] = 100.0 if k < 0 else 100.0 * 0.8 ** (k // 10 + 1)
        s = pd.Series(q, index=idx)
        df, _ = water_year_metrics(s, "local_minimum", drainage_area_sqmi=1.0)
        row = df[df["water_year"] == 1997].iloc[0]
        assert row["recession_k"] == pytest.approx(8.0 / 9.0)
        assert 0.0 < row["recession_k"] < 1.0

    def test_junjul_exceeds_augsep_on_recession_hydrograph(self):
        s, _ = _synthetic_hydrograph(n_years=3)
        for method in METHODS:
            df, _ = _metrics(s, method)
            assert (df["junjul_baseflow_cfs"] > df["augsep_baseflow_cfs"]).all()
            # min 7-day mean can never exceed the Aug-Sep mean
            assert (df["min7_baseflow_cfs"] <= df["augsep_baseflow_cfs"] + 1e-9).all()
            assert df["baseflow_cot_dowy"].between(1, 366).all()

    def test_unknown_method_raises(self):
        s = _daily("1995-10-01", "1997-09-30", 10.0)
        with pytest.raises(ValueError):
            water_year_metrics(s, "part")


# =========================================================================== sec 6 trends
def _metrics_frame(values_by_col: dict, start_wy: int = 1996) -> pd.DataFrame:
    n = len(next(iter(values_by_col.values())))
    df = pd.DataFrame({"water_year": np.arange(start_wy, start_wy + n)})
    for c in TREND_METRICS:
        df[c] = values_by_col.get(c, np.linspace(1.0, 2.0, n))
    return df


class TestTrends:
    def test_increasing_monotone(self):
        vals = 0.5 + 0.005 * np.arange(20)
        out = baseflow_trends(_metrics_frame({"bfi": vals}))
        assert set(out) == set(TREND_METRICS)
        o = out["bfi"]["original"]
        h = out["bfi"]["hamed_rao"]
        assert o["trend"] == "increasing" and o["significant"] is True
        assert h["trend"] == "increasing" and h["significant"] is True
        assert o["slope"] == pytest.approx(0.005)
        assert set(o) == set(mk_to_dict(pmk.original_test(vals)))
        assert set(h) == set(o)

    def test_decreasing_monotone(self):
        vals = 0.9 - 0.004 * np.arange(25)
        out = baseflow_trends(_metrics_frame({"bfi": vals}))
        o = out["bfi"]["original"]
        assert o["trend"] == "decreasing" and o["significant"] is True
        assert out["bfi"]["hamed_rao"]["trend"] == "decreasing"
        assert o["slope"] == pytest.approx(-0.004)
        assert out["bfi"]["slope_pct_per_decade"] < 0

    def test_random_series_not_significant(self):
        vals = np.random.default_rng(0).normal(size=20)  # seed 0 -> p ~ 0.46
        out = baseflow_trends(_metrics_frame({"bfi": vals}))
        assert out["bfi"]["original"]["significant"] is False
        assert out["bfi"]["hamed_rao"]["significant"] is False
        assert out["bfi"]["original"]["trend"] == "no trend"

    def test_matches_pymannkendall(self):
        vals = 100.0 + 0.8 * np.arange(20) + np.random.default_rng(5).normal(0, 3, 20)
        out = baseflow_trends(_metrics_frame({"baseflow_af": vals}))["baseflow_af"]
        ref_o = mk_to_dict(pmk.original_test(vals, alpha=0.10))
        ref_h = mk_to_dict(pmk.hamed_rao_modification_test(vals, alpha=0.10))
        for k, v in ref_o.items():
            assert out["original"][k] == pytest.approx(v) if not isinstance(v, str) else out["original"][k] == v
        for k, v in ref_h.items():
            assert out["hamed_rao"][k] == pytest.approx(v) if not isinstance(v, str) else out["hamed_rao"][k] == v

    def test_alpha_is_forwarded(self):
        vals = np.random.default_rng(0).normal(size=20)
        p = pmk.original_test(vals).p
        loose = baseflow_trends(_metrics_frame({"bfi": vals}), alpha=min(0.99, 2 * p))
        tight = baseflow_trends(_metrics_frame({"bfi": vals}), alpha=p / 2)
        assert loose["bfi"]["original"]["significant"] is True
        assert tight["bfi"]["original"]["significant"] is False

    def test_fewer_than_ten_years_is_none(self):
        out = baseflow_trends(_metrics_frame({"bfi": 0.5 + 0.01 * np.arange(9)}))
        assert all(v is None for v in out.values())

    def test_exactly_ten_years_computed(self):
        out = baseflow_trends(_metrics_frame({"bfi": 0.5 + 0.01 * np.arange(10)}))
        assert out["bfi"] is not None
        assert out["bfi"]["original"]["trend"] == "increasing"

    def test_non_null_count_per_metric(self):
        n = 14
        sparse = np.arange(n, dtype=float)
        sparse[:5] = np.nan  # 9 non-null -> None
        full = np.arange(n, dtype=float)
        out = baseflow_trends(_metrics_frame({"recession_k": sparse, "bfi": full}))
        assert out["recession_k"] is None
        assert out["bfi"] is not None

    def test_slope_pct_per_decade_scale_and_sign(self):
        vals = 50.0 + 0.5 * np.arange(20)  # Sen slope 0.5 / yr
        out = baseflow_trends(_metrics_frame({"baseflow_af": vals}))["baseflow_af"]
        expected = 0.5 * 10.0 / np.median(vals) * 100.0
        assert out["slope_pct_per_decade"] == pytest.approx(expected)
        assert out["slope_pct_per_decade"] > 0

    def test_slope_pct_nan_when_median_zero(self):
        vals = np.maximum(0.0, np.arange(20) - 10.0)  # median 0
        assert np.median(vals) == 0.0
        out = baseflow_trends(_metrics_frame({"bfi": vals}))["bfi"]
        assert np.isnan(out["slope_pct_per_decade"])

    def test_json_serialisable(self):
        out = baseflow_trends(_metrics_frame({"bfi": 0.5 + 0.005 * np.arange(20)}))
        json.dumps(out)  # None / bool / float / str only

    def test_water_year_not_a_key(self):
        out = baseflow_trends(_metrics_frame({"bfi": 0.5 + 0.005 * np.arange(20)}))
        assert "water_year" not in out

    def test_end_to_end_on_computed_metrics(self):
        s, _ = _synthetic_hydrograph(n_years=5)
        df, _ = _metrics(s, "lyne_hollick")
        out = baseflow_trends(df)  # 5 years < 10 -> all None, not an error
        assert all(v is None for v in out.values())


# =========================================================================== sec 7 method_range
def _method_frame(offset: float, slope: float, n: int = 20) -> pd.DataFrame:
    df = pd.DataFrame({"water_year": np.arange(1996, 1996 + n)})
    for j, c in enumerate(TREND_METRICS):
        df[c] = (j + 1) * (offset + slope * np.arange(n))
    return df


class TestMethodRange:
    def test_columns_and_index(self):
        per = {m: _method_frame(5.0 + i, 0.1) for i, m in enumerate(METHODS)}
        out = method_range(per)
        assert list(out.columns) == [
            "min", "median", "max", "n_sig_decreasing", "n_sig_increasing", "n_methods"
        ]
        assert list(out.index) == TREND_METRICS

    def test_min_median_max_of_period_means_and_counts(self):
        per = {
            "lyne_hollick": _method_frame(5.0, 0.1),      # increasing
            "eckhardt": _method_frame(8.0, 0.1),          # increasing
            "local_minimum": _method_frame(30.0, -0.1),   # decreasing
        }
        out = method_range(per)
        means = np.array([per[m]["bfi"].mean() for m in METHODS])
        row = out.loc["bfi"]
        assert row["min"] == pytest.approx(means.min())
        assert row["median"] == pytest.approx(np.median(means))
        assert row["max"] == pytest.approx(means.max())
        assert row["n_sig_increasing"] == 2
        assert row["n_sig_decreasing"] == 1
        assert row["n_methods"] == 3
        assert row["min"] <= row["median"] <= row["max"]

    def test_no_significant_trends_counts_zero(self):
        rng = np.random.default_rng(0)
        per = {}
        for m in METHODS:
            df = pd.DataFrame({"water_year": np.arange(1996, 2016)})
            for c in TREND_METRICS:
                df[c] = rng.normal(size=20) if m == "lyne_hollick" else np.random.default_rng(0).normal(size=20)
            per[m] = df
        out = method_range(per)
        # seed-0 series has p ~ 0.46 so the two identical methods are not significant
        sub = {m: per[m] for m in ("eckhardt", "local_minimum")}
        out2 = method_range(sub)
        assert (out2["n_sig_increasing"] == 0).all()
        assert (out2["n_sig_decreasing"] == 0).all()
        assert (out2["n_methods"] == 2).all()
        assert len(out) == len(TREND_METRICS)

    def test_alpha_forwarded(self):
        vals = np.random.default_rng(0).normal(size=20)
        p = pmk.original_test(vals).p
        df = pd.DataFrame({"water_year": np.arange(1996, 2016)})
        for c in TREND_METRICS:
            df[c] = vals
        loose = method_range({"a": df}, alpha=min(0.99, 2 * p))
        tight = method_range({"a": df}, alpha=p / 2)
        n_loose = loose.loc["bfi", ["n_sig_increasing", "n_sig_decreasing"]].sum()
        n_tight = tight.loc["bfi", ["n_sig_increasing", "n_sig_decreasing"]].sum()
        assert n_loose == 1
        assert n_tight == 0

    def test_single_method(self):
        out = method_range({"lyne_hollick": _method_frame(5.0, 0.1)})
        row = out.loc["bfi"]
        assert row["min"] == row["median"] == row["max"]
        assert row["n_methods"] == 1
