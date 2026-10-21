"""HTTP tests for POST /api/analyze/baseflow via FastAPI TestClient.

Network-free: api.service._fetch_raw is monkeypatched with a seeded synthetic
35-water-year daily record. Contract: docs/baseflow_app_plan.md. One live
smoke test is marked ``network``.
"""

from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
import pandas as pd
import pytest
import requests
from fastapi.testclient import TestClient

from api import service
from api.main import app

client = TestClient(app)

URL = "/api/analyze/baseflow"
SITE = "13340000"
NO_AREA_SITE = "11492550"
SEED = 19
METRIC_KEYS = [
    "bfi",
    "baseflow_af",
    "junjul_baseflow_cfs",
    "augsep_baseflow_cfs",
    "min7_baseflow_cfs",
    "baseflow_cot_dowy",
    "recession_k",
]
ALL = {"lyne_hollick", "eckhardt", "local_minimum"}


# --------------------------------------------------------------------------- #
# Synthetic data (same generator as tests/test_service_baseflow.py)
# --------------------------------------------------------------------------- #
def make_daily(seed: int = SEED, zero_wy: int | None = None, long_gaps: bool = False) -> pd.DataFrame:
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
    f = FakeFetch(daily)
    monkeypatch.setattr(service, "_fetch_raw", f)
    return f


def _reject_constant(token):
    raise ValueError(f"non-finite JSON token {token!r}")


def strict_json(text: str):
    """Parse JSON refusing NaN / Infinity / -Infinity tokens."""
    return json.loads(text, parse_constant=_reject_constant)


def post(**body):
    body.setdefault("site_no", SITE)
    return client.post(URL, json=body)


def finite_floats(o):
    if isinstance(o, dict):
        for v in o.values():
            yield from finite_floats(v)
    elif isinstance(o, list):
        for v in o:
            yield from finite_floats(v)
    elif isinstance(o, float):
        yield o


# --------------------------------------------------------------------------- #
# 200: payload shape
# --------------------------------------------------------------------------- #
def test_full_payload_shape(fetch, monkeypatch):
    monkeypatch.setattr("api.defaults._today", lambda: date(2026, 10, 21))
    r = post()
    assert r.status_code == 200, r.text
    data = strict_json(r.text)
    assert set(data) == {"meta", "metric_info", "methods", "method_range", "skipped_methods", "example"}

    meta = data["meta"]
    assert set(meta) == {
        "site", "units", "window_start", "window_end", "record_start", "record_end",
        "water_years", "eckhardt_bfi_max", "alpha", "regulation", "caveats",
    }
    assert meta["site"]["site_no"] == SITE
    assert "CLEARWATER" in meta["site"]["name"].upper()
    assert meta["units"] == "cfs"
    assert (meta["window_start"], meta["window_end"]) == ("1985-10-01", "2026-09-30")
    # synthetic record only spans WY1991-2025, so results are bounded by the data
    assert meta["water_years"] == list(range(1991, 2026))
    assert meta["eckhardt_bfi_max"] == 0.8 and meta["alpha"] == 0.1
    assert set(meta["regulation"]) == {"level", "reason"}
    assert meta["regulation"]["level"] in {"likely_regulated", "likely_unregulated", "unknown"}
    assert isinstance(meta["caveats"], list) and len(meta["caveats"]) >= 3

    assert [i["key"] for i in data["metric_info"]] == METRIC_KEYS
    assert all(set(i) == {"key", "label", "unit", "description"} for i in data["metric_info"])

    assert {m["method"] for m in data["methods"]} == ALL
    for m in data["methods"]:
        assert set(m) == {"method", "label", "quality", "metrics", "trends"}
        assert set(m["quality"]) == {"n_interpolated", "skipped_runs", "excluded_water_years"}
        assert isinstance(m["quality"]["n_interpolated"], int)
        assert len(m["metrics"]) == 35  # WY1991-2025 (data-bounded)
        assert set(m["metrics"][0]) == {"water_year", *METRIC_KEYS}
        assert [x["water_year"] for x in m["metrics"]] == sorted(x["water_year"] for x in m["metrics"])
        assert set(m["trends"]) == set(METRIC_KEYS)
        t = m["trends"]["augsep_baseflow_cfs"]
        assert set(t) == {"original", "hamed_rao", "slope_pct_per_decade"}
        assert set(t["original"]) == {"trend", "significant", "p_value", "z", "tau", "s", "var_s", "slope", "intercept"}
        assert set(t["hamed_rao"]) == {"trend", "significant", "p_value", "tau", "slope"}

    assert data["skipped_methods"] == []
    assert len(data["method_range"]) == len(METRIC_KEYS)
    assert {r_["metric"] for r_ in data["method_range"]} == set(METRIC_KEYS)
    assert all(
        set(r_) == {"metric", "min", "median", "max", "n_sig_decreasing", "n_sig_increasing", "n_methods"}
        for r_ in data["method_range"]
    )

    ex = data["example"]
    assert set(ex) == {"water_year", "dates", "flow_cfs", "baseflow_cfs"}
    assert ex["water_year"] == 2025
    assert len(ex["dates"]) == len(ex["flow_cfs"]) == 365
    assert set(ex["baseflow_cfs"]) == ALL
    assert all(len(v) == 365 for v in ex["baseflow_cfs"].values())


def test_fetch_called_with_site_and_default_window(fetch, monkeypatch):
    monkeypatch.setattr("api.defaults._today", lambda: date(2026, 10, 21))
    post()
    assert fetch.calls and fetch.calls[0][0] == SITE
    assert str(fetch.calls[0][1])[:10] == "1985-10-01"
    assert str(fetch.calls[0][2])[:10] == "2026-09-30"


def test_methods_subset_and_example_year(fetch):
    r = post(methods=["eckhardt"], eckhardt_bfi_max=0.65, example_water_year=2008, start_date="2000-10-01")
    assert r.status_code == 200, r.text
    d = r.json()
    assert [m["method"] for m in d["methods"]] == ["eckhardt"]
    assert d["methods"][0]["label"] == "Eckhardt filter (BFImax=0.65)"
    assert d["example"]["water_year"] == 2008
    assert len(d["example"]["dates"]) == 366
    assert list(d["example"]["baseflow_cfs"]) == ["eckhardt"]
    assert d["meta"]["water_years"][0] == 2001


def test_skipped_method_reported_when_no_drainage_area(fetch):
    r = post(site_no=NO_AREA_SITE)
    assert r.status_code == 200, r.text
    d = r.json()
    assert {m["method"] for m in d["methods"]} == {"lyne_hollick", "eckhardt"}
    assert [s["method"] for s in d["skipped_methods"]] == ["local_minimum"]
    assert d["skipped_methods"][0]["reason"]


def test_empty_request_body_uses_defaults_only_with_site(fetch):
    assert post().status_code == 200


# --------------------------------------------------------------------------- #
# No NaN tokens
# --------------------------------------------------------------------------- #
def test_json_has_no_nan_tokens_with_hamed_rao_nan(fetch):
    r = post()
    assert r.status_code == 200
    data = strict_json(r.text)
    assert all(math.isfinite(v) for v in finite_floats(data))
    # seed 19 yields NaN Hamed-Rao p-values in the stats module -> must be null
    p = [t["hamed_rao"]["p_value"] for m in data["methods"] for t in m["trends"].values() if t]
    assert any(v is None for v in p)


def test_json_has_no_nan_tokens_with_zero_flow_water_year(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily(zero_wy=2010)))
    r = post()
    assert r.status_code == 200, r.text
    data = strict_json(r.text)
    for m in data["methods"]:
        row = {x["water_year"]: x for x in m["metrics"]}[2010]
        assert row["bfi"] is None and row["baseflow_cot_dowy"] is None
    assert all(math.isfinite(v) for v in finite_floats(data))


def test_strict_loader_rejects_nan_tokens():
    with pytest.raises(ValueError):
        strict_json('{"a": NaN}')
    with pytest.raises(ValueError):
        strict_json('{"a": -Infinity}')


# --------------------------------------------------------------------------- #
# 404 / 422 / 502
# --------------------------------------------------------------------------- #
def test_unknown_site_404(fetch):
    r = post(site_no="00000000")
    assert r.status_code == 404
    assert "00000000" in r.json()["detail"]


@pytest.mark.parametrize(
    "body",
    [
        {"alpha": 0},
        {"alpha": 1},
        {"alpha": -0.2},
        {"alpha": 1.5},
        {"eckhardt_bfi_max": 0},
        {"eckhardt_bfi_max": 1},
        {"eckhardt_bfi_max": 1.2},
        {"eckhardt_bfi_max": -0.5},
        {"methods": []},
        {"methods": ["lyne_hollick", "lyne_hollick"]},
        {"methods": ["bogus"]},
        {"methods": ["eckhardt", "bogus"]},
        {"start_date": "2020-10-01", "end_date": "2020-10-01"},
        {"start_date": "2020-10-01", "end_date": "2010-09-30"},
        {"start_date": "not-a-date"},
        {"example_water_year": "abc"},
    ],
)
def test_bad_request_422(fetch, body):
    r = post(**body)
    assert r.status_code == 422, (body, r.text)


def test_missing_site_no_422(fetch):
    assert client.post(URL, json={}).status_code == 422


@pytest.mark.parametrize("year", [1980, 1995, 2026])
def test_example_year_not_in_results_422(fetch, year):
    r = post(example_water_year=year)
    assert r.status_code == 422, r.text


def test_example_year_incomplete_422(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily(long_gaps=True)))
    assert post(example_water_year=2003).status_code == 422
    # the same data is fine when the example year is a complete one
    assert post(example_water_year=2010).status_code == 200


def test_too_few_water_years_422(fetch):
    r = post(start_date="2013-10-01", end_date="2022-09-30")  # 9 WYs
    assert r.status_code == 422
    assert "at least 10" in r.json()["detail"]


def test_ten_water_years_200(fetch):
    assert post(start_date="2012-10-01", end_date="2022-09-30").status_code == 200


def test_all_methods_skipped_422(fetch):
    r = post(site_no=NO_AREA_SITE, methods=["local_minimum"])
    assert r.status_code == 422


def test_no_data_422(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", lambda *a, **k: pd.DataFrame({"Date": [], "Discharge": []}))
    r = post()
    assert r.status_code == 422
    assert "No data returned" in r.json()["detail"]


@pytest.mark.parametrize(
    "exc",
    [requests.ConnectionError("boom"), requests.Timeout("slow"), requests.HTTPError("503")],
)
def test_upstream_request_error_502(monkeypatch, exc):
    def boom(*a, **k):
        raise exc

    monkeypatch.setattr(service, "_fetch_raw", boom)
    r = post()
    assert r.status_code == 502
    assert r.json()["detail"]


# --------------------------------------------------------------------------- #
# OpenAPI
# --------------------------------------------------------------------------- #
def test_openapi_lists_route():
    spec = client.get("/openapi.json").json()
    assert URL in spec["paths"]
    assert "post" in spec["paths"][URL]
    names = set(spec["components"]["schemas"])
    assert {"BaseflowRequest", "BaseflowResult"} <= names
    props = spec["components"]["schemas"]["BaseflowRequest"]["properties"]
    assert {"site_no", "start_date", "end_date", "methods", "eckhardt_bfi_max", "alpha", "example_water_year"} <= set(props)


# --------------------------------------------------------------------------- #
# Live smoke test
# --------------------------------------------------------------------------- #
@pytest.mark.network
def test_baseflow_real_gauge_smoke():
    r = post(site_no="13340000")
    assert r.status_code == 200, r.text
    data = strict_json(r.text)
    assert len(data["methods"]) == 3
    assert len(data["meta"]["water_years"]) >= 10
    assert data["meta"]["water_years"][0] >= 1996 and data["meta"]["water_years"][-1] <= 2025
    assert data["meta"]["regulation"]["level"] in {"likely_regulated", "likely_unregulated", "unknown"}
    assert data["meta"]["caveats"]
    ex = data["example"]
    assert len(ex["dates"]) in (365, 366)
    assert all(len(v) == len(ex["dates"]) for v in ex["baseflow_cfs"].values())
