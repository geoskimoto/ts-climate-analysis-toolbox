"""Gap-closing tests for ``climate_core.stats.baseflow`` (docs/baseflow_spec.md).

Written from the spec only (not from the implementation) to pin behaviours the
locked suite ``tests/test_baseflow.py`` leaves open. Synthetic data, fixed
seeds, no network.

Spec gaps noted here (not resolved by the spec text):
  * 4.1 says "reflect 30 values" without saying whether the edge sample is
    repeated. The reference below uses numpy ``mode="reflect"`` (edge excluded,
    the usual Nathan & McMahon / R ``EcoHydRology`` reading); ``symmetric``
    (edge included) is checked to differ, so the test is discriminating.
  * 4.1 does not state ``qf[0]``; the reference uses 0.
  * 3: an *exact* 1.00% interpolated share cannot occur for a 365/366-day
    water year (1% = 3.65 / 3.66 days), so the boundary is pinned as
    3 days allowed (0.82%) / 4 days excluded (1.10%).
  * 7a ``n_methods``: the spec never defines it beyond the name; the only
    supportable reading is the number of per-method frames supplied.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pymannkendall as pmk
import pytest
from scipy.stats import theilslopes

from climate_core.stats.baseflow import (
    METHODS,
    baseflow_trends,
    local_minimum,
    lyne_hollick,
    method_range,
    water_year_metrics,
)

AF = 1.9835
METRIC_COLS = [
    "water_year", "bfi", "baseflow_af", "junjul_baseflow_cfs",
    "augsep_baseflow_cfs", "min7_baseflow_cfs", "baseflow_cot_dowy", "recession_k",
]
TREND_METRICS = METRIC_COLS[1:]


def _daily(start, end, value=10.0):
    idx = pd.date_range(start, end, freq="D")
    return pd.Series(np.full(len(idx), float(value)), index=idx)


def _metrics(series, method, **kw):
    if method == "local_minimum":
        kw.setdefault("drainage_area_sqmi", 100.0)
    return water_year_metrics(series, method, **kw)


def _row(df, wy):
    return df.loc[df["water_year"] == wy].iloc[0]


# =========================================================================== 4.1 Lyne-Hollick
def _ref_lh(q, alpha=0.925, passes=3, pad_mode="reflect", directions=None):
    """Differential reference written from spec 4.1 (qf[0] = 0)."""
    q = np.asarray(q, float)
    cur = np.pad(q, 30, mode=pad_mode)
    for i in range(passes):
        fwd = (i % 2 == 0) if directions is None else directions[i] == "f"
        x = cur if fwd else cur[::-1]
        qf = np.zeros_like(x)
        for t in range(1, len(x)):
            v = alpha * qf[t - 1] + (1 + alpha) / 2 * (x[t] - x[t - 1])
            qf[t] = min(max(v, 0.0), x[t])
        b = x - qf
        cur = b if fwd else b[::-1]
    return cur[30:-30]


def _storm_series():
    """80 days: slow recession base plus storms near both ends (idx 4, 40, 75)."""
    rng = np.random.default_rng(3)
    n = 80
    t = np.arange(n)
    q = 20.0 * 0.995 ** t + rng.uniform(0, 0.3, n)
    for pos, amp in ((4, 60.0), (40, 45.0), (75, 70.0)):
        k = np.arange(n - pos)
        q[pos:] += amp * 0.7 ** k
    return q


class TestLyneHollickGaps:
    def test_hand_step_single_pass(self):
        # alpha=0.5 -> (1+alpha)/2 = 0.75. q = 10 x10 then 20 x21 (31 values).
        # Reflected pad puts the step-up at padded index 40; the earlier padded
        # step-down (20->10) gives qf<0 -> clipped to 0. Forward pass at the step:
        #   qf = 0.75*(20-10) = 7.5 -> b = 12.5; next qf = 0.5*7.5 = 3.75 -> b = 16.25;
        #   next qf = 1.875 -> b = 18.125.
        q = np.array([10.0] * 10 + [20.0] * 21)
        b = lyne_hollick(q, alpha=0.5, passes=1)
        np.testing.assert_allclose(b[:10], 10.0, atol=1e-12)
        np.testing.assert_allclose(b[10:13], [12.5, 16.25, 18.125], rtol=1e-12)

    @pytest.mark.parametrize("passes, expected", [(1, 11.0), (2, 10.25), (3, 10.0625)])
    def test_hand_spike_pass_sequence(self, passes, expected):
        # alpha=0.5, q = 10 with one spike q[15]=14 (31 values; mirrored copies are
        # 30 apart so never interact). Pass 1: qf=0.75*4=3 -> b=11, next qf<0 -> 0.
        # Pass 2 (spike now 1): qf=0.75 -> 10.25. Pass 3 (spike 0.25): qf=0.1875 -> 10.0625.
        q = np.full(31, 10.0)
        q[15] = 14.0
        b = lyne_hollick(q, alpha=0.5, passes=passes)
        assert b[15] == pytest.approx(expected, rel=1e-12)
        np.testing.assert_allclose(np.delete(b, 15), 10.0, atol=1e-12)

    def test_defaults_are_alpha_0925_passes_3(self):
        q = _storm_series()
        d = lyne_hollick(q)
        np.testing.assert_allclose(d, lyne_hollick(q, alpha=0.925, passes=3), rtol=1e-12)
        for kw in ({"alpha": 0.9}, {"passes": 1}, {"passes": 2}):
            other = lyne_hollick(q, **kw)
            assert not np.allclose(d, other, rtol=1e-6), kw

    def test_matches_reference_with_events_near_both_ends(self):
        q = _storm_series()
        np.testing.assert_allclose(lyne_hollick(q), _ref_lh(q), rtol=1e-9)
        np.testing.assert_allclose(
            lyne_hollick(q, alpha=0.8, passes=2), _ref_lh(q, 0.8, 2), rtol=1e-9
        )

    def test_reference_is_discriminating_for_order_and_reflection(self):
        q = _storm_series()
        fbf = _ref_lh(q)
        assert not np.allclose(fbf, _ref_lh(q, directions="bfb"), rtol=1e-6)
        assert not np.allclose(fbf, _ref_lh(q, directions="fff"), rtol=1e-6)
        edge_incl = _ref_lh(q, pad_mode="symmetric")
        assert not np.allclose(fbf[:10], edge_incl[:10], rtol=1e-6)

    def test_length_boundary_30_raises_31_works(self):
        with pytest.raises(ValueError):
            lyne_hollick(np.full(30, 5.0))
        b = lyne_hollick(np.full(31, 5.0))
        assert b.shape == (31,) and np.isfinite(b).all()
        np.testing.assert_allclose(b, 5.0)

    @pytest.mark.parametrize("passes", [0, -1])
    def test_passes_below_one_raises(self, passes):
        with pytest.raises(ValueError):
            lyne_hollick(np.full(60, 5.0), passes=passes)


# =========================================================================== 4.3 HYSEP window
def _dip_series(h=100.0):
    s = _daily("1995-10-01", "1999-09-30", h)
    s.loc["1998-01-15"] = 0.0
    return s


class TestHysepWindow:
    # Single zero dip in constant H: days within half-window h=(w-1)/2 of the dip
    # (except the dip) are not minima; baseflow is linear between H and 0, so the
    # total deficit is (h+1)*H = (w+1)/2 * H.
    @pytest.mark.parametrize(
        "area, w",
        [
            (0.01, 3), (1.0, 3), (100.0, 5), (500.0, 5),   # 2N = 0.64, 1.6, 4.02, 5.55
            (1000.0, 7), (2000.0, 7),                       # 6.37, 7.32
            (5000.0, 9), (10000.0, 11), (1e6, 11),          # 8.79, 10.10, 25.4 -> clip
            (2.5 ** 5, 5),    # 2N = 4 exactly -> tie -> larger (5)
            (3.75 ** 5, 7),   # 2N = 6 -> 7
            (5.0 ** 5, 9),    # 2N = 8 -> 9
            (6.25 ** 5, 11),  # 2N = 10 -> 11
        ],
    )
    def test_window_from_area(self, area, w):
        s = _dip_series()
        df, _ = water_year_metrics(s, "local_minimum", drainage_area_sqmi=area)
        total_q = 365 * 100.0 - 100.0
        expected_af = (365 * 100.0 - (w + 1) / 2 * 100.0) * AF
        assert _row(df, 1998)["baseflow_af"] == pytest.approx(expected_af, rel=1e-9), (
            f"window {w} expected; total q {total_q}"
        )

    @pytest.mark.parametrize("area", [0.0, -5.0])
    def test_nonpositive_area_raises(self, area):
        with pytest.raises(ValueError):
            local_minimum(np.full(50, 5.0), area)
        with pytest.raises(ValueError):
            water_year_metrics(_daily("1995-10-01", "1998-09-30"), "local_minimum",
                               drainage_area_sqmi=area)


# =========================================================================== 3 quality policy
class TestQualityBoundaries:
    @pytest.mark.parametrize("method", METHODS)
    def test_run_of_365_days_is_filtered(self, method):
        s = _daily("1996-10-01", "1997-09-30")  # exactly 365 days (non-leap WY1997)
        assert len(s) == 365
        df, qr = _metrics(s, method)
        assert qr.skipped_runs == []
        assert df["water_year"].tolist() == [1997]

    @pytest.mark.parametrize("method", METHODS)
    def test_run_of_364_days_is_skipped(self, method):
        s = _daily("1996-10-01", "1997-09-29")
        assert len(s) == 364
        df, qr = _metrics(s, method)
        assert qr.skipped_runs == [(pd.Timestamp("1996-10-01"), pd.Timestamp("1997-09-29"))]
        assert len(df) == 0

    def test_leading_and_trailing_gaps_never_filled(self):
        s = _daily("1996-09-29", "1997-10-02")
        s.loc["1996-09-29":"1996-09-30"] = np.nan   # leading 2-day gap
        s.loc["1997-10-01":"1997-10-02"] = np.nan   # trailing 2-day gap
        df, qr = _metrics(s, "lyne_hollick")
        assert qr.n_interpolated == 0
        assert qr.skipped_runs == []
        assert df["water_year"].tolist() == [1997]

    @pytest.mark.parametrize("method", METHODS)
    @pytest.mark.parametrize(
        "start, end, wy, days",
        [
            # 365-day year: 3/365 = 0.82% allowed, 4/365 = 1.10% excluded.
            ("1995-10-01", "1998-09-30", 1997, ["1997-01-10", "1997-03-10", "1997-05-10", "1997-07-10"]),
            # 366-day leap year: 3/366 = 0.82% allowed, 4/366 = 1.09% excluded.
            ("1998-10-01", "2001-09-30", 2000, ["2000-01-10", "2000-03-10", "2000-05-10", "2000-07-10"]),
        ],
    )
    def test_one_percent_interpolation_boundary(self, method, start, end, wy, days):
        s = _daily(start, end)
        s.loc[days[:3]] = np.nan
        df, qr = _metrics(s, method)
        assert qr.n_interpolated == 3
        assert wy in df["water_year"].tolist()
        assert wy not in qr.excluded_water_years

        s = _daily(start, end)
        s.loc[days] = np.nan
        df, qr = _metrics(s, method)
        assert qr.n_interpolated == 4
        assert wy not in df["water_year"].tolist()
        assert set(qr.excluded_water_years) == {wy}
        assert isinstance(qr.excluded_water_years[wy], str) and qr.excluded_water_years[wy]

    def test_interpolation_share_is_per_water_year(self):
        s = _daily("1995-10-01", "1999-09-30")
        s.loc[["1997-01-10", "1997-03-10", "1997-05-10"]] = np.nan   # 3 in WY1997
        s.loc[["1998-01-10", "1998-03-10", "1998-05-10"]] = np.nan   # 3 in WY1998
        df, qr = _metrics(s, "lyne_hollick")
        assert qr.n_interpolated == 6
        assert {1997, 1998} <= set(df["water_year"])
        assert qr.excluded_water_years == {}


# =========================================================================== 5 metric windows
def _dip_metrics(dip_date, d=2.0, h=10.0):
    s = _daily("1995-10-01", "1999-09-30", h)
    s.loc[dip_date] = d
    df, _ = _metrics(s, "local_minimum", drainage_area_sqmi=1.0)  # window 3
    return _row(df, 1998)


class TestMetricWindows:
    # Constant H=10 with one dip D=2 (delta=8), window 3: baseflow is H except
    # dip day = D (deficit delta) and both neighbours = (H+D)/2 (deficit delta/2).
    @pytest.mark.parametrize(
        "dip, jj_def, as_def",
        [
            ("1998-05-30", 0.0, 0.0),
            ("1998-05-31", 0.5, 0.0),   # only Jun 1 neighbour is in Jun-Jul
            ("1998-06-01", 1.5, 0.0),   # Jun 1 + Jun 2; May 31 excluded
            ("1998-07-31", 1.5, 0.5),   # Jul 30 + Jul 31 in; Aug 1 belongs to Aug-Sep
            ("1998-08-01", 0.5, 1.5),   # Jul 31 in Jun-Jul; Aug 1 + Aug 2 in Aug-Sep
            ("1998-09-30", 0.0, 1.5),   # Sep 29 + Sep 30; Oct 1 is next WY
        ],
    )
    def test_junjul_and_augsep_window_edges(self, dip, jj_def, as_def):
        delta = 8.0
        r = _dip_metrics(dip)
        assert r["junjul_baseflow_cfs"] == pytest.approx(10.0 - jj_def * delta / 61, rel=1e-12)
        assert r["augsep_baseflow_cfs"] == pytest.approx(10.0 - as_def * delta / 61, rel=1e-12)

    def test_min7_is_seven_day_rolling_mean(self):
        # Affected baseflow: 10, 6, 2, 6, 10 (deficit 2*delta = 16) fits in any
        # window >= 3: 7-day mean = 10 - 16/7. (3-day: 6.0, 5-day: 6.8, 14-day: 8.857.)
        r = _dip_metrics("1998-01-15")
        assert r["min7_baseflow_cfs"] == pytest.approx(10.0 - 16.0 / 7, rel=1e-12)


def _recession_k_series(events):
    """Level 100; each (date, factor) multiplies the level from that date on."""
    s = _daily("1995-10-01", "1999-09-30", 100.0)
    for date, f in sorted(events):
        s.loc[date:] *= f
    return s


def _expected_k(events):
    """Window-3 HYSEP on plateau steps: a down-step A->B on day s gives
    b[s-1] = (A+B)/2 (ratio (A+B)/2A) and b[s] = B (ratio 2B/(A+B)); up-steps
    give only ratios > 1. Keep ratio days with month/day in Jul 15 - Oct 31."""
    level, ratios = 100.0, []
    for date, f in sorted(events):
        if f < 1:
            a, b = level, level * f
            s = pd.Timestamp(date)
            for day, r in ((s - pd.Timedelta(days=1), (a + b) / (2 * a)), (s, 2 * b / (a + b))):
                if (7, 15) <= (day.month, day.day) <= (10, 31) or (day.month, day.day) >= (10, 1) and day.month == 10:
                    ratios.append(r)
        level *= f
    return float(np.median(ratios)) if len(ratios) >= 10 else np.nan


_BASE = [("1998-08-10", 0.9), ("1998-08-25", 0.8), ("1998-09-10", 0.7), ("1998-09-25", 0.85),
         ("1997-12-01", 10.0)]  # Dec up-step lifts the level; ratios > 1 never count


class TestRecessionKWindow:
    @pytest.mark.parametrize(
        "extra, n_ratios",
        [
            ([], 8),
            ([("1998-06-20", 0.5), ("1998-07-14", 0.6)], 8),   # June / Jul 14: outside
            ([("1998-07-15", 0.6)], 9),                        # only Jul 15 itself (Jul 14 out)
            ([("1998-07-16", 0.6)], 10),                       # Jul 15 + Jul 16
            ([("1997-10-31", 0.6)], 10),                       # Oct 30 + Oct 31
            ([("1997-11-01", 0.6)], 9),                        # Oct 31 only (Nov 1 out)
            ([("1997-10-10", 0.9), ("1997-10-20", 0.8), ("1998-06-20", 0.5)], 12),
        ],
    )
    def test_window_and_ten_day_minimum(self, extra, n_ratios):
        events = _BASE + extra
        df, _ = _metrics(_recession_k_series(events), "local_minimum", drainage_area_sqmi=1.0)
        got = _row(df, 1998)["recession_k"]
        exp = _expected_k(events)
        if n_ratios < 10:
            assert np.isnan(exp) and np.isnan(got)
        else:
            assert not np.isnan(exp)
            assert got == pytest.approx(exp, rel=1e-12)


# =========================================================================== 6 trends
def _frame(years, cols):
    df = pd.DataFrame({"water_year": years})
    for c in TREND_METRICS:
        df[c] = cols.get(c, np.linspace(1.0, 2.0, len(years)))
    return df


GAPPED_YEARS = np.array([1996, 1997, 1999, 2003, 2004, 2006, 2007, 2010, 2011, 2012, 2015, 2018])


def _pct(y, x):
    return theilslopes(y, x=x).slope * 10 / np.median(y) * 100


class TestTrendsGaps:
    def test_gapped_years_slope_per_year(self):
        rng = np.random.default_rng(5)
        y = 5.0 + 0.2 * (GAPPED_YEARS - 1996) + rng.normal(0, 0.05, len(GAPPED_YEARS))
        out = baseflow_trends(_frame(GAPPED_YEARS, {"bfi": y}))
        assert out["bfi"]["slope_pct_per_decade"] == pytest.approx(_pct(y, GAPPED_YEARS), rel=1e-9)
        # per-index slope would be clearly different on gapped years
        idx_pct = theilslopes(y).slope * 10 / np.median(y) * 100
        assert abs(idx_pct - out["bfi"]["slope_pct_per_decade"]) > 1.0
        for c in TREND_METRICS[1:]:
            ref = np.linspace(1.0, 2.0, len(GAPPED_YEARS))
            assert out[c]["slope_pct_per_decade"] == pytest.approx(_pct(ref, GAPPED_YEARS), rel=1e-9)

    def test_negative_median_uses_signed_median(self):
        rng = np.random.default_rng(6)
        y = -(10.0 + 0.3 * (GAPPED_YEARS - 1996)) + rng.normal(0, 0.05, len(GAPPED_YEARS))
        assert np.median(y) < 0
        out = baseflow_trends(_frame(GAPPED_YEARS, {"bfi": y}))
        assert out["bfi"]["slope_pct_per_decade"] == pytest.approx(_pct(y, GAPPED_YEARS), rel=1e-9)

    def test_zero_median_gives_nan(self):
        y = np.array([-2.0, -1.0, 0, 0, 0, 0, 0, 0, 1.0, 2.0, 3.0, 4.0])
        assert np.median(y) == 0
        out = baseflow_trends(_frame(GAPPED_YEARS, {"bfi": y}))
        assert np.isnan(out["bfi"]["slope_pct_per_decade"])

    def test_nulls_drop_pairs_and_threshold_counts_non_null(self):
        years = np.arange(1996, 2010)  # 14
        y = 3.0 + 0.1 * np.arange(14)
        y[[2, 7]] = np.nan                       # 12 valid
        z = y.copy()
        z[[1, 3, 9]] = np.nan                    # 9 valid -> None
        out = baseflow_trends(_frame(years, {"bfi": y, "baseflow_af": z}))
        ok = ~np.isnan(y)
        assert out["bfi"]["slope_pct_per_decade"] == pytest.approx(_pct(y[ok], years[ok]), rel=1e-9)
        assert out["baseflow_af"] is None

    def test_duplicate_years_raise(self):
        years = np.array([1996, 1997, 1997] + list(range(1998, 2010)))
        with pytest.raises(ValueError):
            baseflow_trends(_frame(years, {}))

    def test_unsorted_years_raise(self):
        years = np.arange(1996, 2010)
        years[[3, 4]] = years[[4, 3]]
        with pytest.raises(ValueError):
            baseflow_trends(_frame(years, {}))


# =========================================================================== 7 method_range
def _mframe(values, n=20):
    df = pd.DataFrame({"water_year": np.arange(1996, 1996 + n)})
    for c in TREND_METRICS:
        df[c] = values
    return df


class TestMethodRangeCounts:
    def test_sign_and_significance_counts_and_n_methods(self):
        n = 20
        ramp = np.arange(n, dtype=float)
        noise = np.random.default_rng(0).normal(size=n)   # not significant (p ~ 0.46)
        assert pmk.original_test(noise).p > 0.10
        per = {
            "inc_a": _mframe(5 + 0.1 * ramp),
            "inc_b": _mframe(9 + 0.3 * ramp),
            "dec_a": _mframe(30 - 0.2 * ramp),
            "flat": _mframe(np.full(n, 7.0)),
            "noise": _mframe(noise),
        }
        out = method_range(per)
        for c in TREND_METRICS:
            assert out.loc[c, "n_sig_increasing"] == 2
            assert out.loc[c, "n_sig_decreasing"] == 1
            # Spec gap: n_methods undefined; only reading supported = frames supplied.
            assert out.loc[c, "n_methods"] == 5

    def test_counts_match_original_mk_at_alpha(self):
        n = 20
        rng = np.random.default_rng(1)
        per = {f"m{i}": _mframe(0.02 * i * np.arange(n) * (-1) ** i + rng.normal(0, 0.5, n))
               for i in range(5)}
        for alpha in (0.01, 0.10, 0.5):
            out = method_range(per, alpha=alpha)
            inc = dec = 0
            for df in per.values():
                r = pmk.original_test(df["bfi"], alpha=alpha)
                inc += bool(r.h) and r.trend == "increasing"
                dec += bool(r.h) and r.trend == "decreasing"
            assert out.loc["bfi", "n_sig_increasing"] == inc
            assert out.loc["bfi", "n_sig_decreasing"] == dec
