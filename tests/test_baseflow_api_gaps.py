"""Gap-closing tests for the baseflow API/service (written from the contract only).

Contract: docs/baseflow_app_plan.md (incl. "Clarifications") and
docs/baseflow_spec.md. Network-free: ``api.service._fetch_raw`` is
monkeypatched with seeded synthetic data. Expected numbers come from calling
``climate_core.stats.baseflow`` / ``pymannkendall`` directly.
"""

from __future__ import annotations

import json
import math
import warnings
from datetime import date

import numpy as np
import pandas as pd
import pymannkendall as pmk
import pytest
import requests
from fastapi.testclient import TestClient

from api import schemas, service
from api.main import app
from api.service_baseflow import run_baseflow_analysis
from climate_core.catalog import default_catalog
from climate_core.stats import baseflow as bf

warnings.filterwarnings("ignore", category=RuntimeWarning)

client = TestClient(app)
URL = "/api/analyze/baseflow"
SITE = "13340000"          # catalog area 5507 mi2
NO_AREA_SITE = "11492550"  # catalog drainage area missing
SEED = 19
METRIC_KEYS = [
    "bfi", "baseflow_af", "junjul_baseflow_cfs", "augsep_baseflow_cfs",
    "min7_baseflow_cfs", "baseflow_cot_dowy", "recession_k",
]
DEFAULT_ORDER = ["lyne_hollick", "eckhardt", "local_minimum"]
OLD_WIN = {"start_date": "1995-10-01", "end_date": "2025-09-30"}  # pre-1985-default window, WY1996-2025


# --------------------------------------------------------------------------- #
# Synthetic data
# --------------------------------------------------------------------------- #
def make_daily(seed: int = SEED, trend: float = 0.0, extra_gaps: tuple = (), long_gaps: bool = False) -> pd.DataFrame:
    """Daily cfs 1990-10-01..2025-09-30 (WY1991-2025) as Date/Discharge.

    ``trend`` multiplies flow by (1 + trend*(WY-2010)). Small NaN gaps (2, 3, 1
    days) are in WY1999/2007/2016. ``extra_gaps`` = (start, end) strings set NaN.
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("1990-10-01", "2025-09-30", freq="D")
    wy = np.where(dates.month >= 10, dates.year + 1, dates.year)
    wy_start = pd.to_datetime([f"{y - 1}-10-01" for y in wy])
    dowy = np.minimum((dates - wy_start).days.to_numpy(), 364)
    wet = rng.uniform(0.6, 1.4, 35)[wy - 1991]
    peak = (215 + rng.normal(0, 6, 35))[wy - 1991]
    snow = 900.0 * wet * np.exp(-0.5 * ((dowy - peak) / 32.0) ** 2)
    slow = 120.0 * wet * np.exp(-dowy / 200.0) + 60.0
    events = rng.random(len(dates)) < 0.05
    amp = rng.gamma(2.0, 60.0, len(dates)) * events
    storm = np.convolve(amp, np.exp(-np.arange(12) / 2.5))[: len(dates)]
    q = np.maximum(slow + snow + storm + rng.normal(0, 3.0, len(dates)), 5.0)
    q = np.round(q * (1.0 + trend * (wy - 2010)), 2)
    s = pd.Series(q, index=dates)
    for a, b in [("1999-02-10", "1999-02-11"), ("2007-07-04", "2007-07-06"), ("2016-11-20", "2016-11-20")]:
        s[a:b] = np.nan
    for a, b in extra_gaps:
        s[a:b] = np.nan
    return pd.DataFrame({"Date": [d.date() for d in s.index], "Discharge": s.to_numpy()})


class FakeFetch:
    """Fake of api.service._fetch_raw. ``honour_range=False`` returns everything."""

    def __init__(self, df, honour_range=True):
        self.df, self.honour_range = df, honour_range
        self._dt = pd.to_datetime(df["Date"])
        self.calls: list[tuple] = []

    def __call__(self, site_no, start_date, end_date):
        self.calls.append((site_no, start_date, end_date))
        if not self.honour_range:
            return self.df
        m = (self._dt >= pd.Timestamp(str(start_date)[:10])) & (self._dt <= pd.Timestamp(str(end_date)[:10]))
        return self.df[m.to_numpy()].reset_index(drop=True)


@pytest.fixture(scope="module")
def daily():
    return make_daily()


@pytest.fixture
def fetch(monkeypatch, daily):
    f = FakeFetch(daily)
    monkeypatch.setattr(service, "_fetch_raw", f)
    return f


def window_series(df, start="1995-10-01", end="2025-09-30") -> pd.Series:
    s = pd.Series(pd.to_numeric(df["Discharge"], errors="coerce").to_numpy(dtype=float), index=pd.to_datetime(df["Date"]))
    return s.loc[start:end]


def patch_site(monkeypatch, site_no, **cols):
    cat = default_catalog()
    df = cat.df.copy()
    for k, v in cols.items():
        df[k] = df[k].astype(float)
        df.loc[df["site_no"] == site_no, k] = v
    monkeypatch.setattr(cat, "df", df)


def run(**kw) -> dict:
    kw.setdefault("site_no", SITE)
    return run_baseflow_analysis(schemas.BaseflowRequest(**kw)).model_dump()


def post(**body):
    body.setdefault("site_no", SITE)
    return client.post(URL, json=body)


def by(rows, key):
    return {r[key]: r for r in rows}


def arr(xs):
    return np.array([np.nan if v is None else v for v in xs], dtype=float)


def strict_json(text):
    def bad(tok):
        raise ValueError(tok)
    return json.loads(text, parse_constant=bad)


def per_method_expected(df, bfi_max=0.8, area=5507.0):
    out = {}
    for m in DEFAULT_ORDER:
        kw = {"bfi_max": bfi_max} if m == "eckhardt" else {}
        out[m] = bf.water_year_metrics(window_series(df), m, drainage_area_sqmi=area, **kw)[0]
    return out


# --------------------------------------------------------------------------- #
# (1) eckhardt_bfi_max propagation
# --------------------------------------------------------------------------- #
def test_bfimax_changes_eckhardt_metrics_label_and_example(fetch, daily):
    # explicit old window: intent (bfi_max propagation) is unrelated to the default window, and
    # the expected series below are computed over window_series' default (WY1996-2025)
    d5, d8 = run(eckhardt_bfi_max=0.5, **OLD_WIN), run(**OLD_WIN)
    e5, e8 = by(d5["methods"], "method")["eckhardt"], by(d8["methods"], "method")["eckhardt"]
    assert e5["label"] == "Eckhardt filter (BFImax=0.50)"
    assert e8["label"] == "Eckhardt filter (BFImax=0.80)"
    bfi5, bfi8 = arr([r["bfi"] for r in e5["metrics"]]), arr([r["bfi"] for r in e8["metrics"]])
    assert not np.allclose(bfi5, bfi8)
    exp5 = bf.water_year_metrics(window_series(daily), "eckhardt", bfi_max=0.5)[0]
    np.testing.assert_allclose(bfi5, exp5["bfi"].to_numpy(), rtol=1e-9)
    # example hydrograph (WY2025 has no gaps -> raw series)
    raw = window_series(daily).loc["2024-10-01":"2025-09-30"].to_numpy()
    ex5 = arr(d5["example"]["baseflow_cfs"]["eckhardt"])
    ex8 = arr(d8["example"]["baseflow_cfs"]["eckhardt"])
    assert not np.allclose(ex5, ex8)
    cleaned = window_series(daily).interpolate(limit_area="inside")
    full = bf.eckhardt(cleaned.to_numpy(), bfi_max=0.5)
    exp_ex = pd.Series(full, index=cleaned.index).loc["2024-10-01":"2025-09-30"].to_numpy()
    np.testing.assert_allclose(ex5, exp_ex, rtol=1e-9)
    assert raw.shape == ex5.shape
    # other methods are unaffected
    for m in ("lyne_hollick", "local_minimum"):
        np.testing.assert_allclose(arr(d5["example"]["baseflow_cfs"][m]), arr(d8["example"]["baseflow_cfs"][m]))
    assert d5["meta"]["eckhardt_bfi_max"] == 0.5


# --------------------------------------------------------------------------- #
# (2) alpha end to end
# --------------------------------------------------------------------------- #
@pytest.fixture
def trended(monkeypatch):
    df = make_daily(trend=-0.002)  # lyne/eckhardt baseflow_af have original MK p ~0.07-0.09
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(df))
    return df


def test_schema_default_alpha_and_bounds():
    assert schemas.BaseflowRequest(site_no=SITE).alpha == 0.10
    for bad in (0, 1, 0.0, 1.0):
        with pytest.raises(ValueError):
            schemas.BaseflowRequest(site_no=SITE, alpha=bad)
    for ok in (0.001, 0.999):
        assert schemas.BaseflowRequest(site_no=SITE, alpha=ok).alpha == ok


@pytest.mark.parametrize("bad", [0, 1, -0.5, 2])
def test_http_alpha_bounds_422(fetch, bad):
    assert post(alpha=bad).status_code == 422


@pytest.mark.parametrize("alpha", [0.05, 0.2])
def test_meta_alpha_equals_request(fetch, alpha):
    assert run(alpha=alpha)["meta"]["alpha"] == alpha


def test_alpha_flips_significance_and_method_range_counts(trended):
    exp10, exp05 = (
        {m: bf.baseflow_trends(df, alpha=a) for m, df in per_method_expected(trended).items()}
        for a in (0.10, 0.05)
    )
    # precondition: baseflow_af is significant at 0.10 but not 0.05 for lyne_hollick
    assert exp10["lyne_hollick"]["baseflow_af"]["original"]["significant"]
    assert not exp05["lyne_hollick"]["baseflow_af"]["original"]["significant"]
    # explicit old window: the precondition (p ~0.07-0.09 for baseflow_af) holds only over WY1996-2025
    d10, d05 = run(alpha=0.10, **OLD_WIN), run(alpha=0.05, **OLD_WIN)
    for d, exp in ((d10, exp10), (d05, exp05)):
        for x in d["methods"]:
            for k, e in exp[x["method"]].items():
                assert x["trends"][k]["original"]["significant"] == e["original"]["significant"], (x["method"], k)
                assert x["trends"][k]["hamed_rao"]["significant"] == e["hamed_rao"]["significant"], (x["method"], k)
    r10, r05 = by(d10["method_range"], "metric"), by(d05["method_range"], "metric")
    exp_r10 = bf.method_range(per_method_expected(trended), alpha=0.10)
    exp_r05 = bf.method_range(per_method_expected(trended), alpha=0.05)
    for metric in METRIC_KEYS:
        for k in ("n_sig_decreasing", "n_sig_increasing"):
            assert r10[metric][k] == int(exp_r10.loc[metric, k])
            assert r05[metric][k] == int(exp_r05.loc[metric, k])
    tot = lambda r: r["baseflow_af"]["n_sig_decreasing"] + r["baseflow_af"]["n_sig_increasing"]
    assert tot(r10) > tot(r05)


# --------------------------------------------------------------------------- #
# (3) ordering
# --------------------------------------------------------------------------- #
def test_default_methods_order(fetch):
    d = run()
    assert [m["method"] for m in d["methods"]] == DEFAULT_ORDER
    assert list(d["example"]["baseflow_cfs"]) == DEFAULT_ORDER or set(d["example"]["baseflow_cfs"]) == set(DEFAULT_ORDER)


@pytest.mark.parametrize(
    "req",
    [
        ["local_minimum", "eckhardt", "lyne_hollick"],
        ["eckhardt", "lyne_hollick", "local_minimum"],
        ["local_minimum", "lyne_hollick"],
        ["eckhardt", "local_minimum"],
    ],
)
def test_methods_follow_request_order(fetch, req):
    assert [m["method"] for m in run(methods=req)["methods"]] == req


def test_request_order_minus_skipped(fetch):
    d = run(site_no=NO_AREA_SITE, methods=["local_minimum", "eckhardt", "lyne_hollick"])
    assert [m["method"] for m in d["methods"]] == ["eckhardt", "lyne_hollick"]
    d = run(site_no=NO_AREA_SITE, methods=["eckhardt", "local_minimum", "lyne_hollick"])
    assert [m["method"] for m in d["methods"]] == ["eckhardt", "lyne_hollick"]
    assert [s["method"] for s in d["skipped_methods"]] == ["local_minimum"]


def test_metric_info_and_method_range_follow_spec_order(fetch):
    d = run()
    assert [i["key"] for i in d["metric_info"]] == METRIC_KEYS
    assert [r["metric"] for r in d["method_range"]] == METRIC_KEYS


def test_excluded_water_years_sorted_ascending(monkeypatch):
    gaps = (("2012-05-01", "2012-05-10"), ("2003-03-01", "2003-03-10"), ("1998-08-01", "1998-08-10"),
            ("2021-01-05", "2021-01-15"))
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily(extra_gaps=gaps)))
    for methods in (["lyne_hollick"], ["eckhardt", "lyne_hollick"]):
        d = run(methods=methods)
        for x in d["methods"]:
            ys = [e["water_year"] for e in x["quality"]["excluded_water_years"]]
            assert {1998, 2003, 2012, 2021} <= set(ys)
            assert ys == sorted(ys)
        assert not ({1998, 2003, 2012, 2021} & set(d["meta"]["water_years"]))


def test_meta_water_years_from_first_method_that_ran(fetch):
    d = run(site_no=NO_AREA_SITE, methods=["local_minimum", "eckhardt", "lyne_hollick"])
    assert d["meta"]["water_years"] == [r["water_year"] for r in d["methods"][0]["metrics"]]
    assert d["methods"][0]["method"] == "eckhardt"


# --------------------------------------------------------------------------- #
# (4) record bounds, null dates, errors
# --------------------------------------------------------------------------- #
def test_record_bounds_are_raw_fetched_min_max(monkeypatch, daily):
    monkeypatch.setattr("api.defaults._today", lambda: date(2026, 10, 21))
    f = FakeFetch(daily, honour_range=False)  # returns 1990-10-01..2025-09-30 whatever the window
    monkeypatch.setattr(service, "_fetch_raw", f)
    m = run()["meta"]
    assert (m["record_start"], m["record_end"]) == ("1990-10-01", "2025-09-30")
    assert (m["window_start"], m["window_end"]) == ("1985-10-01", "2026-09-30")


def test_record_bounds_for_record_shorter_than_window(monkeypatch, daily):
    sub = daily[(pd.to_datetime(daily["Date"]) >= "1996-03-15") & (pd.to_datetime(daily["Date"]) <= "2024-06-20")]
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(sub.reset_index(drop=True), honour_range=False))
    m = run()["meta"]
    assert (m["record_start"], m["record_end"]) == ("1996-03-15", "2024-06-20")


def test_explicit_null_dates_map_to_defaults(fetch, monkeypatch):
    monkeypatch.setattr("api.defaults._today", lambda: date(2026, 10, 21))
    r = post(start_date=None, end_date=None)
    assert r.status_code == 200, r.text
    assert str(fetch.calls[0][1])[:10] == "1985-10-01" and str(fetch.calls[0][2])[:10] == "2026-09-30"
    meta = r.json()["meta"]
    assert (meta["window_start"], meta["window_end"]) == ("1985-10-01", "2026-09-30")
    req = schemas.BaseflowRequest(site_no=SITE, start_date=None, end_date=None)
    assert req.start_date is None or str(req.start_date) == "1985-10-01"


def test_example_year_not_complete_422_http(fetch):
    for y in (1990, 2026):
        assert post(example_water_year=y).status_code == 422
    # explicit null -> latest complete
    r = post(example_water_year=None)
    assert r.status_code == 200 and r.json()["example"]["water_year"] == 2025


@pytest.mark.parametrize("ret", [None, pd.DataFrame({"Date": [], "Discharge": []}), pd.DataFrame()])
def test_fetch_none_or_empty_is_422_not_500(monkeypatch, ret):
    monkeypatch.setattr(service, "_fetch_raw", lambda *a, **k: ret)
    with pytest.raises(ValueError, match="No data returned"):
        run()
    r = post()
    assert r.status_code == 422
    assert "No data returned" in r.json()["detail"]


# --------------------------------------------------------------------------- #
# (5) Hamed-Rao slope, bad values, area, literal
# --------------------------------------------------------------------------- #
def test_hamed_rao_slope_is_hr_slope_not_tau(trended):
    d = run()
    checked = 0
    for x in d["methods"]:
        y = arr([r["baseflow_af"] for r in x["metrics"]])
        hr = pmk.hamed_rao_modification_test(y, alpha=0.10)
        got = x["trends"]["baseflow_af"]["hamed_rao"]
        assert abs(hr.slope - hr.Tau) > 1.0  # precondition: slope (af/yr) and tau clearly differ
        assert got["slope"] == pytest.approx(float(hr.slope), rel=1e-9)
        assert got["tau"] == pytest.approx(float(hr.Tau), rel=1e-9)
        assert got["trend"] == hr.trend
        assert got["significant"] == bool(hr.h)
        checked += 1
    assert checked == 3


def _dated_idx(ex, date):
    return ex["dates"].index(date)


def test_negative_nan_and_none_flows_are_null_in_example(monkeypatch, daily):
    df = daily.copy()
    df["Discharge"] = df["Discharge"].astype(object)
    ix = {d: i for i, d in enumerate(df["Date"].astype(str))}
    df.iat[ix["2025-03-20"], 1] = -5.0
    df.iat[ix["2025-03-11"], 1] = float("nan")
    df.iat[ix["2025-04-02"], 1] = None
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(df))
    ex = run()["example"]
    for day in ("2025-03-20", "2025-03-11", "2025-04-02"):
        assert ex["flow_cfs"][_dated_idx(ex, day)] is None, day  # null, not 0.0 and not interpolated
    assert ex["flow_cfs"][_dated_idx(ex, "2025-03-21")] is not None
    for m, b in ex["baseflow_cfs"].items():
        assert all(v is not None and math.isfinite(v) for v in b), m
    # baseflow computed on the cleaned (interpolated) series
    s = window_series(df)
    s[s < 0] = np.nan
    cleaned = s.interpolate(limit_area="inside")
    exp = pd.Series(bf.lyne_hollick(cleaned.to_numpy()), index=cleaned.index).loc["2024-10-01":"2025-09-30"].to_numpy()
    np.testing.assert_allclose(arr(ex["baseflow_cfs"]["lyne_hollick"]), exp, rtol=1e-9, atol=1e-9)
    r = post()
    assert r.status_code == 200
    strict_json(r.text)


@pytest.mark.parametrize("area", [0.0, -10.0])
def test_nonpositive_drainage_area_skips_local_minimum(fetch, monkeypatch, area):
    patch_site(monkeypatch, SITE, drainage_area_sqmi=area)
    d = run()
    assert [m["method"] for m in d["methods"]] == ["lyne_hollick", "eckhardt"]
    assert [s["method"] for s in d["skipped_methods"]] == ["local_minimum"]
    assert d["skipped_methods"][0]["reason"].strip()
    r = post(methods=["local_minimum"])
    assert r.status_code == 422


@pytest.mark.parametrize("name", ["part", "PART", "lyne-hollick", ""])
def test_unknown_method_names_rejected(fetch, name):
    with pytest.raises(ValueError):
        schemas.BaseflowRequest(site_no=SITE, methods=[name])
    assert post(methods=[name]).status_code == 422
    assert post(methods=["eckhardt", name]).status_code == 422


# --------------------------------------------------------------------------- #
# (6) caveats
# --------------------------------------------------------------------------- #
def test_caveats_three_themes(fetch):
    cav = [c.lower() for c in run()["meta"]["caveats"]]
    assert any("hydrograph" in c and "groundwater" in c for c in cav)
    assert any("snowmelt" in c and "bank storage" in c and "reservoir" in c for c in cav)
    assert any("sensitive" in c and "start" in c and "end" in c for c in cav)
    assert len(set(cav)) == len(cav)


# --------------------------------------------------------------------------- #
# (7) route-level error mapping
# --------------------------------------------------------------------------- #
def test_route_404(fetch):
    r = post(site_no="00000000")
    assert r.status_code == 404 and "00000000" in r.json()["detail"]


@pytest.mark.parametrize("body", [
    {"alpha": 1}, {"eckhardt_bfi_max": 0}, {"methods": []}, {"methods": ["part"]},
    {"start_date": "2020-01-01", "end_date": "2020-01-01"}, {"example_water_year": 1900},
    {"start_date": "2013-10-01", "end_date": "2022-09-30"},
])
def test_route_422(fetch, body):
    assert post(**body).status_code == 422


@pytest.mark.parametrize("exc", [requests.ConnectionError("x"), requests.Timeout("x"), requests.HTTPError("x")])
def test_route_502(monkeypatch, exc):
    def boom(*a, **k):
        raise exc
    monkeypatch.setattr(service, "_fetch_raw", boom)
    r = post()
    assert r.status_code == 502 and r.json()["detail"]
