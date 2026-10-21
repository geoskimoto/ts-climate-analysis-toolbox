"""Second round of gap-closing tests (contract-only; no implementation read).

Contract: docs/baseflow_app_plan.md (+ Clarifications), docs/regulated_gauges_plan.md,
docs/baseflow_spec.md. Loader tests point ``climate_core.catalog.regulation._REGULATED_PATH``
at crafted temp CSVs (naming convention as in tests/test_regulated_gauges.py) and
restore it afterwards. Service tests monkeypatch ``api.service._fetch_raw`` with
seeded synthetic data; no network.
"""

from __future__ import annotations

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import schemas, service
from api.main import app
from climate_core.catalog import regulation as reg
from climate_core.catalog.regulation import regulation_hint

from tests.test_service_baseflow import NO_AREA_SITE, SITE, FakeFetch, make_daily, patch_site, run

client = TestClient(app)
URL = "/api/analyze/baseflow"
COLUMNS = ["site_no", "name", "regulator", "kind", "confidence", "source_url"]
KINDS = ["dam_release", "diversion", "reservoir_storage", "canal_or_return_flow", "multiple"]
CURATED = "13341000"   # contract anchor: below Dworshak Dam
UNLISTED = "13340000"  # contract: Clearwater at Orofino is NOT regulated / not curated
REGULATED_NAMES = [
    "LITTLE CR BELOW X", "BIG DAM SITE", "OWYHEE RESERVOIR", "MAIN CANAL", "PAYETTE LAKE OUTLET", "A CR AT FOO DAM",
]


def post(**body):
    body.setdefault("site_no", SITE)
    return client.post(URL, json=body)


# --------------------------------------------------------------------------- #
# (1) curated precedence over keyword names
# --------------------------------------------------------------------------- #
def test_precondition_anchor_listed_and_orofino_not():
    g = reg.regulated_gauges()
    assert CURATED in g and UNLISTED not in g


@pytest.mark.parametrize("name", REGULATED_NAMES)
@pytest.mark.parametrize("area", [5.0, 150.0, 5000.0, None])
def test_curated_site_beats_keyword_name_and_small_area(name, area):
    g = reg.regulated_gauges()[CURATED]
    h = regulation_hint(name, area, site_no=CURATED)
    assert h.level == "regulated"
    assert h.reason.startswith("Known regulation:")
    assert h.reason == f"Known regulation: {g.regulator} ({g.kind}, {g.confidence} confidence; curated list)."


@pytest.mark.parametrize("name", REGULATED_NAMES)
@pytest.mark.parametrize("area", [5.0, 5000.0])
def test_unlisted_site_with_keyword_name_is_likely_regulated(name, area):
    h = regulation_hint(name, area, site_no=UNLISTED)
    assert h.level == "likely_regulated"
    assert not h.reason.startswith("Known regulation:")


def test_curated_site_with_plain_name_still_regulated():
    assert regulation_hint("PLAIN CR", 5.0, site_no=CURATED).level == "regulated"


# --------------------------------------------------------------------------- #
# (2) loader: source_url retention and validation
# --------------------------------------------------------------------------- #
GOOD = ["13340000", "Clearwater R", "Dworshak Dam", "dam_release", "high", "https://example.org/x"]


def _row(**kw):
    d = dict(zip(COLUMNS, GOOD))
    d.update(kw)
    return [d[c] for c in COLUMNS]


@pytest.fixture
def load_from(tmp_path):
    original = reg._REGULATED_PATH

    def _load(rows):
        p = tmp_path / "rg.csv"
        p.write_text("\n".join([",".join(COLUMNS)] + [",".join(r) for r in rows]) + "\n", encoding="utf-8")
        reg._REGULATED_PATH = p
        reg.regulated_gauges.cache_clear()
        return reg.regulated_gauges()

    yield _load
    reg._REGULATED_PATH = original
    reg.regulated_gauges.cache_clear()


def test_source_url_retained_from_crafted_csv(load_from):
    rows = [
        _row(site_no="10000001", source_url="https://a.example.org/one?x=1"),
        _row(site_no="10000002", confidence="medium", source_url="http://b.example.org/two"),
        _row(site_no="10000003", kind="diversion", source_url="https://c.example.org/three/four.pdf"),
    ]
    g = load_from(rows)
    for r in rows:
        assert g[r[0]].source_url == r[5]


def test_source_url_retained_from_real_csv():
    df = pd.read_csv(reg.__file__.replace("regulation.py", "data/regulated_gauges.csv"), dtype=str, keep_default_na=False)
    g = reg.regulated_gauges()
    med = df[df["confidence"] == "medium"]
    pick = [df.iloc[0], df.iloc[len(df) // 2], df.iloc[-1]]
    if len(med):
        pick[1] = med.iloc[0]
    assert any(r["confidence"] == "medium" for r in pick) or not len(med)
    for r in pick:
        assert g[r["site_no"]].source_url == r["source_url"]


@pytest.mark.parametrize(
    "url",
    ["http://", "https:// bad", "ftp://x.org", "https://", "x https://y.org"],
)
def test_malformed_source_url_rejected_naming_site(load_from, url):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(source_url=url)])


def test_surrounding_whitespace_in_cell_is_stripped(load_from):
    g = load_from([_row(source_url=" https://example.org/a ")])
    assert g["13340000"].source_url == "https://example.org/a"


def test_valid_url_with_query_accepted(load_from):
    g = load_from([_row(source_url="https://example.org/a?b=c")])
    assert g["13340000"].source_url == "https://example.org/a?b=c"


@pytest.mark.parametrize("kind", ["other", "Dam_Release", "DIVERSION", "dam release", "dam", ""])
def test_kind_outside_contract_rejected(load_from, kind):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(kind=kind)])


@pytest.mark.parametrize("kind", KINDS)
def test_each_contract_kind_accepted(load_from, kind):
    assert load_from([_row(kind=kind)])["13340000"].kind == kind


@pytest.mark.parametrize("conf", ["low", "High", "MEDIUM", "", "none"])
def test_confidence_outside_contract_rejected(load_from, conf):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(confidence=conf)])


@pytest.mark.parametrize("conf", ["high", "medium"])
def test_each_confidence_accepted(load_from, conf):
    assert load_from([_row(confidence=conf)])["13340000"].confidence == conf


# --------------------------------------------------------------------------- #
# (3) BaseflowRequest schema bounds / literals
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("field, default", [("alpha", 0.10), ("eckhardt_bfi_max", 0.80)])
def test_defaults_exact_and_bounds(field, default):
    assert getattr(schemas.BaseflowRequest(site_no=SITE), field) == default
    for bad in (0, 1, 0.0, 1.0, -0.1, 1.1):
        with pytest.raises(ValidationError):
            schemas.BaseflowRequest(site_no=SITE, **{field: bad})
    for ok in (0.001, 0.999):
        assert getattr(schemas.BaseflowRequest(site_no=SITE, **{field: ok}), field) == ok


@pytest.mark.parametrize("field", ["alpha", "eckhardt_bfi_max"])
@pytest.mark.parametrize("bad", [0, 1, -0.1, 1.1])
def test_bounds_http_422(monkeypatch, field, bad):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily()))
    assert post(**{field: bad}).status_code == 422


@pytest.mark.parametrize("field", ["alpha", "eckhardt_bfi_max"])
@pytest.mark.parametrize("ok", [0.001, 0.999])
def test_bounds_http_accepts_interior(monkeypatch, field, ok):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily()))
    assert post(**{field: ok}).status_code == 200


@pytest.mark.parametrize("m", ["lyne_hollick", "eckhardt", "local_minimum"])
def test_methods_literal_accepts_three_names(m):
    assert list(schemas.BaseflowRequest(site_no=SITE, methods=[m]).methods) == [m]


@pytest.mark.parametrize("m", ["part", "HYSEP", "", "Eckhardt", "lyne-hollick", "local minimum"])
def test_methods_literal_rejects_others(monkeypatch, m):
    with pytest.raises(ValidationError):
        schemas.BaseflowRequest(site_no=SITE, methods=[m])
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily()))
    assert post(methods=[m]).status_code == 422


# --------------------------------------------------------------------------- #
# (4) example_water_year valid in the calendar but not among complete WYs
# --------------------------------------------------------------------------- #
@pytest.fixture
def gappy(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily(long_gaps=True)))


# 1995 dropped: it is a complete year under the 1985 default start (1990 covers "before the record")
@pytest.mark.parametrize("year", [2003, 2004, 1990, 2026])
def test_example_year_not_complete_http_422(gappy, year):
    assert post(example_water_year=year).status_code == 422


# 1995 dropped: it is a complete year under the 1985 default start (1990 covers "before the record")
@pytest.mark.parametrize("year", [2003, 2004, 1990, 2026])
def test_example_year_not_complete_service_valueerror(gappy, year):
    with pytest.raises(ValueError):
        run(example_water_year=year)


def test_example_year_complete_neighbours_ok(gappy):
    assert run(example_water_year=2002)["example"]["water_year"] == 2002
    assert run(example_water_year=2005)["example"]["water_year"] == 2005


# --------------------------------------------------------------------------- #
# (5) meta.water_years and request order
# Complete-WY sets depend only on the data (gap policy), not on the method, so the
# three methods cannot realistically yield different sets; only the request-order
# consequence is observable.
# --------------------------------------------------------------------------- #
def test_meta_water_years_follow_first_method_that_ran_with_skip(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily(long_gaps=True)))
    d = run(site_no=NO_AREA_SITE, methods=["local_minimum", "eckhardt"])
    assert [m["method"] for m in d["methods"]] == ["eckhardt"]
    assert d["meta"]["water_years"] == [r["water_year"] for r in d["methods"][0]["metrics"]]
    assert 2003 not in d["meta"]["water_years"] and 2004 not in d["meta"]["water_years"]
    assert [e["water_year"] for e in d["methods"][0]["quality"]["excluded_water_years"]] == [2003, 2004]


@pytest.mark.parametrize("order", [["local_minimum", "eckhardt", "lyne_hollick"], ["lyne_hollick", "eckhardt", "local_minimum"]])
def test_meta_water_years_independent_of_request_order(monkeypatch, order):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily(long_gaps=True)))
    d = run(methods=order)
    assert d["meta"]["water_years"] == [r["water_year"] for r in d["methods"][0]["metrics"]]
    assert d["meta"]["water_years"] == [y for y in range(1991, 2026) if y not in (2003, 2004)]
    first_excluded = [e["water_year"] for e in d["methods"][0]["quality"]["excluded_water_years"]]
    assert first_excluded == [2003, 2004]


# --------------------------------------------------------------------------- #
# (6) n_methods counts methods that ran
# --------------------------------------------------------------------------- #
def test_n_methods_excludes_skipped_methods(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily()))
    d = run(site_no=NO_AREA_SITE)  # three requested, local_minimum skipped
    assert len(d["method_range"]) == 7
    assert all(r["n_methods"] == 2 for r in d["method_range"])
    assert all(r["n_sig_decreasing"] + r["n_sig_increasing"] <= 2 for r in d["method_range"])


def test_n_methods_when_only_one_of_two_ran(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily()))
    patch_site(monkeypatch, SITE, drainage_area_sqmi=float("nan"))
    d = run(methods=["lyne_hollick", "local_minimum"])
    assert [s["method"] for s in d["skipped_methods"]] == ["local_minimum"]
    assert all(r["n_methods"] == 1 for r in d["method_range"])
    for r in d["method_range"]:
        assert r["min"] == r["median"] == r["max"]


def test_n_methods_equals_requested_when_none_skipped(monkeypatch):
    monkeypatch.setattr(service, "_fetch_raw", FakeFetch(make_daily()))
    assert all(r["n_methods"] == 3 for r in run()["method_range"])
