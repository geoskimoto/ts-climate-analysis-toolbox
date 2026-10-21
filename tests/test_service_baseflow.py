"""Unit tests for api.service_baseflow.run_baseflow_analysis (no network).

Spec: docs/baseflow_app_plan.md (API contract) and docs/baseflow_spec.md. The
USGS fetch (api.service._fetch_raw) is monkeypatched with a seeded synthetic
35-water-year daily record (snowmelt hydrograph + storms + a few small gaps).
Expected numbers are obtained by calling climate_core.stats.baseflow directly.
"""

from __future__ import annotations

import math
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pytest

from api import schemas, service
from api.service_baseflow import run_baseflow_analysis
from climate_core.catalog import default_catalog
from climate_core.catalog.regulation import regulation_hint
from climate_core.stats import baseflow as bf

warnings.filterwarnings("ignore", category=RuntimeWarning)

SITE = "13340000"        # Clearwater R at Orofino: catalog area 5507 mi2
NO_AREA_SITE = "11492550"  # catalog drainage area is missing
SEED = 19  # chosen so that Hamed-Rao yields NaN p-values for some metrics
METRIC_KEYS = [
    "bfi",
    "baseflow_af",
    "junjul_baseflow_cfs",
    "augsep_baseflow_cfs",
    "min7_baseflow_cfs",
    "baseflow_cot_dowy",
    "recession_k",
]
METHOD_LABELS = {
    "lyne_hollick": "Lyne-Hollick filter",
    "local_minimum": "Local minimum (HYSEP-style)",
}
ALL = ["lyne_hollick", "eckhardt", "local_minimum"]
DEFAULT_WYS = list(range(1996, 2026))
DATA_WYS = list(range(1991, 2026))  # full synthetic record


# --------------------------------------------------------------------------- #
# Synthetic data
# --------------------------------------------------------------------------- #
def make_daily(seed: int = SEED, zero_wy: int | None = None, long_gaps: bool = False) -> pd.DataFrame:
    """Daily cfs for 1990-10-01..2025-09-30 (WY1991-2025) as Date/Discharge.

    Small NaN gaps (2, 3 and 1 days, in WY1999/2007/2016) are always present.
    ``long_gaps`` adds two 10-day gaps in WY2003/WY2004 that leave a <365-day
    run in between. ``zero_wy`` sets one whole water year to 0 cfs.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1990-10-01", "2025-09-30", freq="D")
    wy = np.where(dates.month >= 10, dates.year + 1, dates.year)
    wy_start = pd.to_datetime([f"{y - 1}-10-01" for y in wy])
    dowy = np.minimum((dates - wy_start).days.to_numpy(), 364)
    wet_by_wy = rng.uniform(0.6, 1.4, 35)
    peak_by_wy = 215 + rng.normal(0, 6, 35)
    wet = wet_by_wy[wy - 1991]
    peak = peak_by_wy[wy - 1991]
    snow = 900.0 * wet * np.exp(-0.5 * ((dowy - peak) / 32.0) ** 2)
    slow = 120.0 * wet * np.exp(-dowy / 200.0) + 60.0
    events = rng.random(len(dates)) < 0.05
    amp = rng.gamma(2.0, 60.0, len(dates)) * events
    storm = np.convolve(amp, np.exp(-np.arange(12) / 2.5))[: len(dates)]
    q = np.round(np.maximum(slow + snow + storm + rng.normal(0, 3.0, len(dates)), 5.0), 2)
    s = pd.Series(q, index=dates)
    if zero_wy is not None:
        s[wy == zero_wy] = 0.0
    for a, b in [("1999-02-10", "1999-02-11"), ("2007-07-04", "2007-07-06"), ("2016-11-20", "2016-11-20")]:
        s[a:b] = np.nan
    if long_gaps:
        s["2003-03-01":"2003-03-10"] = np.nan
        s["2003-12-01":"2003-12-10"] = np.nan
    return pd.DataFrame({"Date": [d.date() for d in s.index], "Discharge": s.to_numpy()})


class FakeFetch:
    """Stand-in for api.service._fetch_raw; honours the requested date range."""

    def __init__(self, df: pd.DataFrame):
        self.df = df
        self._dt = pd.to_datetime(df["Date"])
        self.calls: list[tuple] = []

    def __call__(self, site_no, start_date, end_date):
        self.calls.append((site_no, start_date, end_date))
        m = (self._dt >= pd.Timestamp(str(start_date)[:10])) & (self._dt <= pd.Timestamp(str(end_date)[:10]))
        return self.df[m.to_numpy()].reset_index(drop=True)


@pytest.fixture(scope="module")
def daily() -> pd.DataFrame:
    return make_daily()


@pytest.fixture
def fetch(monkeypatch, daily) -> FakeFetch:
    # Default window is dynamic (api.defaults); pin "today" so it is 1985-10-01..2026-09-30.
    monkeypatch.setattr("api.defaults._today", lambda: date(2026, 10, 21))
    f = FakeFetch(daily)
    monkeypatch.setattr(service, "_fetch_raw", f)
    return f


def window_series(df: pd.DataFrame, start="1985-10-01", end="2026-09-30") -> pd.Series:
    s = pd.Series(df["Discharge"].to_numpy(dtype=float), index=pd.to_datetime(df["Date"]))
    return s.loc[start:end]


def patch_site(monkeypatch, site_no: str, **cols):
    """Override catalog columns of one site (catalog singleton's frame)."""
    cat = default_catalog()
    df = cat.df.copy()
    for k, v in cols.items():
        df[k] = df[k].astype(object) if isinstance(v, str) else df[k].astype(float)
        df.loc[df["site_no"] == site_no, k] = v
    monkeypatch.setattr(cat, "df", df)


def run(**kw) -> dict:
    kw.setdefault("site_no", SITE)
    res = run_baseflow_analysis(schemas.BaseflowRequest(**kw))
    assert isinstance(res, schemas.BaseflowResult)
    return res.model_dump()


def by(rows, key):
    return {r[key]: r for r in rows}


def nn(v):
    """NaN/inf -> None, like the API contract."""
    if isinstance(v, (float, np.floating)) and not math.isfinite(v):
        return None
    return v


def walk_floats(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from walk_floats(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from walk_floats(v)
    elif isinstance(o, float):
        yield o


# --------------------------------------------------------------------------- #
# Defaults and request validation
# --------------------------------------------------------------------------- #
def test_request_defaults(monkeypatch):
    monkeypatch.setattr("api.defaults._today", lambda: date(2026, 10, 21))
    r = schemas.BaseflowRequest(site_no=SITE)
    assert str(r.start_date) == "1985-10-01"
    assert str(r.end_date) == "2026-09-30"
    assert list(r.methods) == ALL or set(r.methods) == set(ALL)
    assert r.eckhardt_bfi_max == 0.80
    assert r.alpha == 0.10
    assert r.example_water_year is None


def test_defaults_window_wy1996_2025(fetch):
    d = run()
    assert [c[0] for c in fetch.calls][0] == SITE
    assert str(fetch.calls[0][1])[:10] == "1985-10-01"
    assert str(fetch.calls[0][2])[:10] == "2026-09-30"
    m = d["meta"]
    assert m["window_start"] == "1985-10-01"
    assert m["window_end"] == "2026-09-30"
    # synthetic record only spans WY1991-2025, so results are bounded by the data
    assert m["water_years"] == DATA_WYS
    assert m["units"] == "cfs"
    assert m["eckhardt_bfi_max"] == 0.80
    assert m["alpha"] == 0.10
    assert m["site"]["site_no"] == SITE
    assert m["record_start"] == "1990-10-01"
    assert m["record_end"] == "2025-09-30"
    assert {x["method"] for x in d["methods"]} == set(ALL)
    assert d["skipped_methods"] == []
    for x in d["methods"]:
        assert [r["water_year"] for r in x["metrics"]] == DATA_WYS


def test_meta_water_years_are_those_of_first_method_that_ran(fetch):
    d = run()
    assert d["meta"]["water_years"] == [r["water_year"] for r in d["methods"][0]["metrics"]]


def test_custom_window_is_passed_to_fetch_and_reported(fetch):
    d = run(start_date="2000-10-01", end_date="2020-09-30")
    assert str(fetch.calls[0][1])[:10] == "2000-10-01"
    assert str(fetch.calls[0][2])[:10] == "2020-09-30"
    assert d["meta"]["window_start"] == "2000-10-01"
    assert d["meta"]["window_end"] == "2020-09-30"
    assert d["meta"]["water_years"] == list(range(2001, 2021))


def test_partial_leading_water_year_not_in_results(fetch):
    d = run(start_date="1995-06-01")
    assert d["meta"]["water_years"] == DEFAULT_WYS
    for x in d["methods"]:
        assert [r["water_year"] for r in x["metrics"]] == DEFAULT_WYS


@pytest.mark.parametrize("field", ["alpha", "eckhardt_bfi_max"])
@pytest.mark.parametrize("bad", [0, 0.0, 1, 1.0, -0.1, 1.5])
def test_open_unit_interval_params_rejected(field, bad):
    with pytest.raises(ValueError):
        schemas.BaseflowRequest(site_no=SITE, **{field: bad})


@pytest.mark.parametrize("methods", [[], ["lyne_hollick", "lyne_hollick"], ["nope"], ["eckhardt", "PART"]])
def test_bad_methods_rejected(methods):
    with pytest.raises(ValueError):
        schemas.BaseflowRequest(site_no=SITE, methods=methods)


@pytest.mark.parametrize(
    "start, end",
    [("2020-10-01", "2020-10-01"), ("2020-10-01", "2010-09-30")],
)
def test_end_not_after_start_rejected(start, end):
    with pytest.raises(ValueError):
        schemas.BaseflowRequest(site_no=SITE, start_date=start, end_date=end)


def test_unknown_site_raises_keyerror(fetch):
    with pytest.raises(KeyError):
        run_baseflow_analysis(schemas.BaseflowRequest(site_no="00000000"))


def test_empty_fetch_raises_valueerror(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", lambda *a, **k: pd.DataFrame({"Date": [], "Discharge": []}))
    with pytest.raises(ValueError, match="No data returned"):
        run_baseflow_analysis(schemas.BaseflowRequest(site_no=SITE))


# --------------------------------------------------------------------------- #
# Methods subset, labels, kwargs
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("subset", [["lyne_hollick"], ["eckhardt"], ["local_minimum"], ["eckhardt", "lyne_hollick"]])
def test_methods_subset(fetch, subset):
    d = run(methods=subset)
    assert {x["method"] for x in d["methods"]} == set(subset)
    assert set(d["example"]["baseflow_cfs"]) == set(subset)
    assert d["skipped_methods"] == []
    assert all(r["n_methods"] == len(subset) for r in d["method_range"])


def test_labels(fetch):
    d = run()
    lab = {x["method"]: x["label"] for x in d["methods"]}
    assert lab["lyne_hollick"] == "Lyne-Hollick filter"
    assert lab["local_minimum"] == "Local minimum (HYSEP-style)"
    assert lab["eckhardt"] == "Eckhardt filter (BFImax=0.80)"


@pytest.mark.parametrize("bfi_max, text", [(0.6, "0.60"), (0.65, "0.65"), (0.25, "0.25")])
def test_eckhardt_label_shows_used_bfimax(fetch, bfi_max, text):
    d = run(methods=["eckhardt"], eckhardt_bfi_max=bfi_max)
    assert d["methods"][0]["label"] == f"Eckhardt filter (BFImax={text})"
    assert d["meta"]["eckhardt_bfi_max"] == bfi_max


def test_eckhardt_bfimax_is_used_in_metrics(fetch, daily):
    s = window_series(daily)
    expected, _ = bf.water_year_metrics(s, "eckhardt", bfi_max=0.6)
    default, _ = bf.water_year_metrics(s, "eckhardt", bfi_max=0.8)
    d = run(methods=["eckhardt"], eckhardt_bfi_max=0.6)
    got = [r["bfi"] for r in d["methods"][0]["metrics"]]
    np.testing.assert_allclose(got, expected["bfi"].to_numpy(), rtol=1e-9)
    assert not np.allclose(got, default["bfi"].to_numpy())


# --------------------------------------------------------------------------- #
# Metrics match the stats module
# --------------------------------------------------------------------------- #
def expected_metrics(daily, method, **kw):
    s = window_series(daily)
    area = 5507.0 if method == "local_minimum" else None
    return bf.water_year_metrics(s, method, drainage_area_sqmi=area, **kw)


@pytest.mark.parametrize("method", ALL)
def test_metrics_equal_stats_module(fetch, daily, method):
    kw = {"bfi_max": 0.8} if method == "eckhardt" else {}
    exp, _ = expected_metrics(daily, method, **kw)
    d = run()
    rows = by(d["methods"], "method")[method]["metrics"]
    assert [r["water_year"] for r in rows] == exp["water_year"].tolist()
    for col in METRIC_KEYS:
        got = np.array([np.nan if r[col] is None else r[col] for r in rows], dtype=float)
        np.testing.assert_allclose(got, exp[col].to_numpy(dtype=float), rtol=1e-9, atol=1e-12, equal_nan=True)


def test_metric_row_keys_and_order(fetch):
    d = run()
    for x in d["methods"]:
        years = [r["water_year"] for r in x["metrics"]]
        assert years == sorted(years) and len(set(years)) == len(years)
        for r in x["metrics"]:
            assert list(r) == ["water_year"] + METRIC_KEYS or set(r) == {"water_year", *METRIC_KEYS}
            assert isinstance(r["water_year"], int)


# --------------------------------------------------------------------------- #
# metric_info
# --------------------------------------------------------------------------- #
def test_metric_info_order_and_keys(fetch):
    d = run()
    info = d["metric_info"]
    assert [i["key"] for i in info] == METRIC_KEYS
    for i in info:
        assert set(i) == {"key", "label", "unit", "description"}
        assert all(isinstance(i[k], str) for k in i)
        assert i["label"].strip() and i["description"].strip()


# --------------------------------------------------------------------------- #
# Skipped local_minimum
# --------------------------------------------------------------------------- #
def test_local_minimum_skipped_when_no_area(fetch):
    cat_site = default_catalog().get(NO_AREA_SITE)
    assert cat_site.drainage_area_sqmi is None or pd.isna(cat_site.drainage_area_sqmi)
    d = run(site_no=NO_AREA_SITE)
    assert {x["method"] for x in d["methods"]} == {"lyne_hollick", "eckhardt"}
    assert [s["method"] for s in d["skipped_methods"]] == ["local_minimum"]
    assert isinstance(d["skipped_methods"][0]["reason"], str) and d["skipped_methods"][0]["reason"].strip()
    assert set(d["example"]["baseflow_cfs"]) == {"lyne_hollick", "eckhardt"}
    assert all(r["n_methods"] == 2 for r in d["method_range"])


def test_local_minimum_skipped_when_area_patched_away(fetch, monkeypatch):
    patch_site(monkeypatch, SITE, drainage_area_sqmi=float("nan"))
    d = run(methods=["lyne_hollick", "local_minimum"])
    assert [x["method"] for x in d["methods"]] == ["lyne_hollick"]
    assert [s["method"] for s in d["skipped_methods"]] == ["local_minimum"]


def test_all_requested_methods_skipped_raises(fetch):
    with pytest.raises(ValueError):
        run_baseflow_analysis(schemas.BaseflowRequest(site_no=NO_AREA_SITE, methods=["local_minimum"]))


def test_local_minimum_uses_catalog_area(fetch, monkeypatch, daily):
    patch_site(monkeypatch, SITE, drainage_area_sqmi=3.0)  # small area -> narrower window
    s = window_series(daily)
    exp, _ = bf.water_year_metrics(s, "local_minimum", drainage_area_sqmi=3.0)
    d = run(methods=["local_minimum"])
    got = [r["bfi"] for r in d["methods"][0]["metrics"]]
    np.testing.assert_allclose(got, exp["bfi"].to_numpy(), rtol=1e-9)


# --------------------------------------------------------------------------- #
# Too few water years
# --------------------------------------------------------------------------- #
def test_nine_water_years_rejected(fetch):
    with pytest.raises(ValueError, match="at least 10"):
        run(start_date="2013-10-01", end_date="2022-09-30")


def test_ten_water_years_accepted(fetch):
    d = run(start_date="2012-10-01", end_date="2022-09-30")
    assert d["meta"]["water_years"] == list(range(2013, 2023))
    assert all(v is not None for x in d["methods"] for v in [x["trends"]["bfi"]])


# --------------------------------------------------------------------------- #
# Trends
# --------------------------------------------------------------------------- #
MK_KEYS = {"trend", "significant", "p_value", "z", "tau", "s", "var_s", "slope", "intercept"}
HR_KEYS = {"trend", "significant", "p_value", "tau", "slope"}


def test_trends_keys_and_shapes(fetch):
    d = run()
    for x in d["methods"]:
        assert set(x["trends"]) == set(METRIC_KEYS)
        for k, t in x["trends"].items():
            assert t is not None  # 30 WYs, all metrics have >= 10 values
            assert set(t) == {"original", "hamed_rao", "slope_pct_per_decade"}
            assert set(t["original"]) == MK_KEYS
            assert set(t["hamed_rao"]) == HR_KEYS
            assert t["original"]["trend"] in {"increasing", "decreasing", "no trend"}
            assert t["hamed_rao"]["trend"] in {"increasing", "decreasing", "no trend"}
            assert isinstance(t["original"]["significant"], bool)
            assert isinstance(t["hamed_rao"]["significant"], bool)


@pytest.mark.parametrize("method", ALL)
def test_trends_equal_stats_module(fetch, daily, method):
    kw = {"bfi_max": 0.8} if method == "eckhardt" else {}
    exp_df, _ = expected_metrics(daily, method, **kw)
    exp = bf.baseflow_trends(exp_df, alpha=0.10)
    got = by(run()["methods"], "method")[method]["trends"]
    for k, e in exp.items():
        assert got[k]["original"]["trend"] == e["original"]["trend"]
        assert got[k]["original"]["significant"] == e["original"]["significant"]
        assert got[k]["original"]["p_value"] == pytest.approx(e["original"]["p_value"], rel=1e-9)
        assert got[k]["hamed_rao"]["trend"] == e["hamed_rao"]["trend"]
        assert got[k]["slope_pct_per_decade"] == pytest.approx(nn(e["slope_pct_per_decade"]), rel=1e-9)


def test_alpha_is_applied_to_trends(fetch, daily):
    exp_df, _ = expected_metrics(daily, "lyne_hollick")
    for alpha in (0.01, 0.5):
        exp = bf.baseflow_trends(exp_df, alpha=alpha)
        got = by(run(alpha=alpha)["methods"], "method")["lyne_hollick"]["trends"]
        for k, e in exp.items():
            assert got[k]["original"]["significant"] == e["original"]["significant"]
            assert got[k]["hamed_rao"]["significant"] == e["hamed_rao"]["significant"]


def test_hamed_rao_nan_p_value_becomes_none(fetch, daily):
    # Explicit old window (WY1996-2025): the NaN precondition depends on seed-19 statistics
    # over that window; the longer default window no longer yields NaN p-values.
    old = {"start_date": "1995-10-01", "end_date": "2025-09-30"}
    nan_cases = []
    for m in ALL:
        kw = {"bfi_max": 0.8} if m == "eckhardt" else {}
        area = 5507.0 if m == "local_minimum" else None
        s = window_series(daily, old["start_date"], old["end_date"])
        e = bf.baseflow_trends(bf.water_year_metrics(s, m, drainage_area_sqmi=area, **kw)[0])
        nan_cases += [(m, k) for k, v in e.items() if v and math.isnan(v["hamed_rao"]["p_value"])]
    assert nan_cases, "fixture precondition: seed must yield NaN Hamed-Rao p-values"
    d = by(run(**old)["methods"], "method")
    for m, k in nan_cases:
        assert d[m]["trends"][k]["hamed_rao"]["p_value"] is None
    # and every non-NaN case stays a finite float in [0, 1]
    for x in d.values():
        for k, t in x["trends"].items():
            p = t["hamed_rao"]["p_value"]
            assert p is None or (isinstance(p, float) and 0.0 <= p <= 1.0)


# --------------------------------------------------------------------------- #
# method_range
# --------------------------------------------------------------------------- #
def test_method_range_matches_stats_module(fetch, daily):
    per = {}
    for m in ALL:
        kw = {"bfi_max": 0.8} if m == "eckhardt" else {}
        per[m] = expected_metrics(daily, m, **kw)[0]
    exp = bf.method_range(per, alpha=0.10)
    d = run()
    rows = by(d["method_range"], "metric")
    assert set(rows) == set(METRIC_KEYS)
    assert len(d["method_range"]) == len(METRIC_KEYS)
    for metric, e in exp.iterrows():
        r = rows[metric]
        assert set(r) == {"metric", "min", "median", "max", "n_sig_decreasing", "n_sig_increasing", "n_methods"}
        for k in ("min", "median", "max"):
            assert r[k] == pytest.approx(nn(e[k]), rel=1e-9)
        assert r["n_sig_decreasing"] == int(e["n_sig_decreasing"])
        assert r["n_sig_increasing"] == int(e["n_sig_increasing"])
        assert r["n_methods"] == 3


def test_method_range_consistent_with_per_method_means(fetch):
    d = run()
    for r in d["method_range"]:
        means = []
        for x in d["methods"]:
            vals = [row[r["metric"]] for row in x["metrics"] if row[r["metric"]] is not None]
            means.append(np.mean(vals))
        assert r["min"] == pytest.approx(min(means), rel=1e-9)
        assert r["max"] == pytest.approx(max(means), rel=1e-9)
        assert r["median"] == pytest.approx(float(np.median(means)), rel=1e-9)
        assert r["min"] <= r["median"] <= r["max"]
        assert 0 <= r["n_sig_decreasing"] + r["n_sig_increasing"] <= r["n_methods"]


def test_method_range_sig_counts_match_per_method_trends(fetch):
    d = run()
    for r in d["method_range"]:
        dec = inc = 0
        for x in d["methods"]:
            t = x["trends"][r["metric"]]
            if t and t["original"]["significant"]:
                dec += t["original"]["trend"] == "decreasing"
                inc += t["original"]["trend"] == "increasing"
        assert (r["n_sig_decreasing"], r["n_sig_increasing"]) == (dec, inc)


# --------------------------------------------------------------------------- #
# Quality block
# --------------------------------------------------------------------------- #
def test_quality_shapes_and_values_small_gaps(fetch, daily):
    d = run()
    for x in d["methods"]:
        q = x["quality"]
        assert set(q) == {"n_interpolated", "skipped_runs", "excluded_water_years"}
        assert isinstance(q["n_interpolated"], int)
        assert q["n_interpolated"] == 6  # 2 + 3 + 1 gap days, all <= 3 days
        assert q["skipped_runs"] == []
        assert q["excluded_water_years"] == []


def test_quality_with_long_gaps_matches_module(monkeypatch):
    df = make_daily(long_gaps=True)
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(df))
    _, rep = bf.water_year_metrics(window_series(df), "lyne_hollick")
    assert 2003 in rep.excluded_water_years  # precondition from the stats module
    d = run(methods=["lyne_hollick"])
    q = d["methods"][0]["quality"]
    assert q["n_interpolated"] == rep.n_interpolated
    assert [(r["start"], r["end"]) for r in q["skipped_runs"]] == [
        (str(a.date()), str(b.date())) for a, b in rep.skipped_runs
    ]
    assert len(q["skipped_runs"]) >= 1
    assert {e["water_year"]: e["reason"] for e in q["excluded_water_years"]} == rep.excluded_water_years
    assert all(isinstance(e["reason"], str) and e["reason"] for e in q["excluded_water_years"])
    assert 2003 not in d["meta"]["water_years"]
    assert 2003 not in [r["water_year"] for r in d["methods"][0]["metrics"]]


def test_example_incomplete_water_year_rejected(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily(long_gaps=True)))
    with pytest.raises(ValueError):
        run(methods=["lyne_hollick"], example_water_year=2003)


# --------------------------------------------------------------------------- #
# NaN -> null
# --------------------------------------------------------------------------- #
def test_all_zero_water_year_gives_nulls_and_no_nonfinite(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily(zero_wy=2010)))
    d = run()
    for x in d["methods"]:
        row = by(x["metrics"], "water_year")[2010]  # spec: zero total flow -> NaN bfi and cot_dowy
        assert row["bfi"] is None
        assert row["baseflow_cot_dowy"] is None
    bad = [v for v in walk_floats(d) if not math.isfinite(v)]
    assert bad == []


def test_no_nonfinite_floats_in_default_result(fetch):
    assert [v for v in walk_floats(run()) if not math.isfinite(v)] == []


# --------------------------------------------------------------------------- #
# Example year
# --------------------------------------------------------------------------- #
def test_example_defaults_to_latest_complete_water_year(fetch, daily):
    ex = run()["example"]
    assert ex["water_year"] == 2025
    assert ex["dates"][0] == "2024-10-01" and ex["dates"][-1] == "2025-09-30"
    assert len(ex["dates"]) == 365
    raw = window_series(daily).loc["2024-10-01":"2025-09-30"]
    np.testing.assert_allclose(ex["flow_cfs"], raw.to_numpy(), rtol=1e-9)


def test_example_latest_complete_when_window_ends_mid_year(fetch):
    ex = run(end_date="2020-03-31")["example"]
    assert ex["water_year"] == 2019


def test_example_selected_year_leap_length_and_equal_series(fetch):
    ex = run(example_water_year=2008)["example"]  # WY2008 contains Feb 29, 2008
    assert ex["water_year"] == 2008
    assert ex["dates"][0] == "2007-10-01" and ex["dates"][-1] == "2008-09-30"
    assert len(ex["dates"]) == 366
    assert len(ex["flow_cfs"]) == 366
    assert set(ex["baseflow_cfs"]) == set(ALL)
    for m, b in ex["baseflow_cfs"].items():
        assert len(b) == 366, m


def test_example_baseflow_bounded_by_flow(fetch):
    ex = run()["example"]
    for m, b in ex["baseflow_cfs"].items():
        for q, v in zip(ex["flow_cfs"], b):
            if q is not None and v is not None:
                assert -1e-9 <= v <= q + 1e-9, m


# 1990: record starts 1990-10-01 (WY1990 absent); 1995 is now inside the 1985-start default window
@pytest.mark.parametrize("bad", [1980, 1990, 2026, 2100])
def test_example_year_outside_results_rejected(fetch, bad):
    with pytest.raises(ValueError):
        run(example_water_year=bad)


def test_example_year_in_window_is_accepted_at_edges(fetch):
    assert run(example_water_year=1996)["example"]["water_year"] == 1996
    assert run(example_water_year=2025)["example"]["water_year"] == 2025


def test_example_baseflow_uses_cleaned_interpolated_series(fetch, daily):
    """WY1999 has a 2-day gap; baseflow must come from the interpolated series."""
    s = window_series(daily)
    assert s.loc["1999-02-10":"1999-02-11"].isna().all()
    cleaned = s.interpolate(method="linear", limit_area="inside")
    sl = slice(pd.Timestamp("1998-10-01"), pd.Timestamp("1999-09-30"))
    expected = {
        "lyne_hollick": bf.lyne_hollick(cleaned.to_numpy()),
        "eckhardt": bf.eckhardt(cleaned.to_numpy(), bfi_max=0.8),
        "local_minimum": bf.local_minimum(cleaned.to_numpy(), 5507.0),
    }
    ex = run(example_water_year=1999)["example"]
    assert len(ex["dates"]) == 365
    for m, full in expected.items():
        exp = pd.Series(full, index=cleaned.index).loc[sl].to_numpy()
        got = np.array([np.nan if v is None else v for v in ex["baseflow_cfs"][m]], dtype=float)
        assert not np.isnan(got).any(), m  # interpolated days are filled, not null
        np.testing.assert_allclose(got, exp, rtol=1e-9, atol=1e-9)
    # flow outside the gap equals the raw record
    raw = s.loc[sl]
    got_q = np.array([np.nan if v is None else v for v in ex["flow_cfs"]], dtype=float)
    ok = ~raw.isna().to_numpy()
    np.testing.assert_allclose(got_q[ok], raw.to_numpy()[ok], rtol=1e-9)


# --------------------------------------------------------------------------- #
# Caveats and regulation
# --------------------------------------------------------------------------- #
def test_caveats_cover_three_required_themes(fetch):
    cav = [c.lower() for c in run()["meta"]["caveats"]]
    assert cav and all(isinstance(c, str) and c.strip() for c in cav)
    assert any("hydrograph" in c and "groundwater" in c for c in cav)
    assert any("snowmelt" in c and "bank storage" in c and "reservoir" in c for c in cav)
    assert any("sensitive" in c and "start" in c for c in cav)


def test_regulation_block_default_site(fetch):
    reg = run()["meta"]["regulation"]
    site = default_catalog().get(SITE)
    exp = regulation_hint(site.name, site.drainage_area_sqmi)
    assert reg == {"level": exp.level, "reason": exp.reason}
    assert reg["level"] == "unknown"  # 5507 mi2, no regulated keyword in name


def test_regulation_block_small_unregulated(fetch, monkeypatch):
    patch_site(monkeypatch, SITE, drainage_area_sqmi=50.0)
    assert run()["meta"]["regulation"]["level"] == "likely_unregulated"


def test_regulation_block_regulated_name(fetch, monkeypatch):
    patch_site(monkeypatch, SITE, name="CLEARWATER RIVER BELOW DWORSHAK DAM")
    reg = run()["meta"]["regulation"]
    assert reg["level"] == "likely_regulated"
    assert "heuristic" in reg["reason"].lower()


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #
def test_repeat_calls_identical(fetch):
    assert run() == run()
