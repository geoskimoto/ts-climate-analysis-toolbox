"""Backend tests for the regulation filter (contract: docs/regulation_filter_plan.md).

Offline, TestClient only. Written before the implementation.
"""

import pytest
from fastapi.testclient import TestClient

from api import schemas
from api.main import app
from climate_core.catalog.regulation import regulation_hint

client = TestClient(app)

LEVELS = ("regulated", "likely_regulated", "likely_unregulated", "unknown")
SITE_KEYS = {"site_no", "name", "basin", "state", "lat", "long", "drainage_area_sqmi", "elevation_ft"}
REG_KEYS = {"regulation_level", "regulation_reason"}


def _sites(**params):
    r = client.get("/api/sites", params={"limit": 2000, **params})
    assert r.status_code == 200, r.text
    return r.json()


def _ids(sites):
    return [s["site_no"] for s in sites]


@pytest.fixture(scope="module")
def all_sites():
    return _sites()


def _is_subsequence(sub, full):
    it = iter(full)
    return all(x in it for x in sub)


# (1) list payload ----------------------------------------------------------
def test_list_items_have_regulation_fields(all_sites):
    assert len(all_sites) > 800
    for s in all_sites:
        assert SITE_KEYS <= set(s)
        assert REG_KEYS <= set(s)
        assert s["regulation_level"] in LEVELS
        assert isinstance(s["regulation_reason"], str) and s["regulation_reason"].strip()


def test_level_matches_regulation_hint_for_all_sites(all_sites):
    for s in all_sites:
        h = regulation_hint(s["name"], s["drainage_area_sqmi"], site_no=s["site_no"])
        assert s["regulation_level"] == h.level, s["site_no"]
        assert s["regulation_reason"] == h.reason, s["site_no"]


# (2) single site -----------------------------------------------------------
def test_get_site_regulated_known():
    r = client.get("/api/sites/13341000")
    assert r.status_code == 200
    d = r.json()
    assert SITE_KEYS <= set(d) and REG_KEYS <= set(d)
    assert d["regulation_level"] == "regulated"
    assert "Known regulation" in d["regulation_reason"]


def test_get_site_not_regulated():
    d = client.get("/api/sites/13340000").json()
    assert d["regulation_level"] in LEVELS and d["regulation_level"] != "regulated"
    assert d["regulation_reason"].strip()


def test_get_site_still_404():
    assert client.get("/api/sites/00000000").status_code == 404


def test_get_site_matches_list_entry(all_sites):
    for s in all_sites[:25]:
        d = client.get(f"/api/sites/{s['site_no']}").json()
        assert d["regulation_level"] == s["regulation_level"]
        assert d["regulation_reason"] == s["regulation_reason"]


# (3) filter ----------------------------------------------------------------
def test_filter_regulated_only():
    got = _sites(regulation="regulated")
    assert got and all(s["regulation_level"] == "regulated" for s in got)
    ids = set(_ids(got))
    assert {"13341000", "14105700"} <= ids


@pytest.mark.parametrize("level", LEVELS)
def test_filter_each_level_only_that_level(level):
    for s in _sites(regulation=level):
        assert s["regulation_level"] == level


def test_filter_comma_list():
    got = _sites(regulation="regulated,likely_regulated")
    assert got
    assert {s["regulation_level"] for s in got} == {"regulated", "likely_regulated"}


def test_filter_whitespace_and_empty_items_ignored():
    a = _sites(regulation=" regulated , ,likely_regulated")
    b = _sites(regulation="regulated,likely_regulated")
    assert _ids(a) == _ids(b)


def test_filter_duplicates_harmless():
    assert _ids(_sites(regulation="regulated,regulated,regulated")) == _ids(_sites(regulation="regulated"))


def test_filter_empty_and_absent_equal_no_filter(all_sites):
    assert _ids(_sites(regulation="")) == _ids(all_sites)
    assert _ids(_sites()) == _ids(all_sites)


def test_union_of_single_levels_is_everything_and_disjoint(all_sites):
    parts = [set(_ids(_sites(regulation=lv))) for lv in LEVELS]
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            assert not (parts[i] & parts[j])
    assert set().union(*parts) == set(_ids(all_sites))


@pytest.mark.parametrize("bad", ["bogus", "regulated,bogus", "Regulated", "bogus,nope"])
def test_unknown_level_422_names_bad_value(bad):
    r = client.get("/api/sites", params={"regulation": bad})
    assert r.status_code == 422
    text = str(r.json()["detail"])
    for item in (x.strip() for x in bad.split(",")):
        if item not in LEVELS:
            assert item in text


def test_filter_and_state():
    got = _sites(regulation="regulated", state="WA")
    assert got and all(s["state"] == "WA" and s["regulation_level"] == "regulated" for s in got)
    expected = [s["site_no"] for s in _sites(state="WA") if s["regulation_level"] == "regulated"]
    assert _ids(got) == expected


def test_filter_and_query():
    got = _sites(regulation="regulated", query="CLEARWATER")
    assert "13341000" in _ids(got)
    assert all("CLEARWATER" in s["name"].upper() and s["regulation_level"] == "regulated" for s in got)
    expected = [s["site_no"] for s in _sites(query="CLEARWATER") if s["regulation_level"] == "regulated"]
    assert _ids(got) == expected


def test_filter_and_basin(all_sites):
    basin = next(s["basin"] for s in all_sites if s["site_no"] == "14105700")
    got = _sites(regulation="regulated", basin=basin)
    assert "14105700" in _ids(got)
    assert all(s["basin"] == basin and s["regulation_level"] == "regulated" for s in got)
    expected = [s["site_no"] for s in _sites(basin=basin) if s["regulation_level"] == "regulated"]
    assert _ids(got) == expected


def test_filter_applied_before_limit(all_sites):
    got = _sites(regulation="regulated", limit=5)
    assert len(got) == 5
    assert all(s["regulation_level"] == "regulated" for s in got)
    total = len(_sites(regulation="regulated"))
    assert len(_sites(regulation="regulated", limit=total)) == total
    assert _ids(got) == _ids(_sites(regulation="regulated"))[:5]


@pytest.mark.parametrize("flt", ["regulated", "regulated,likely_regulated", "unknown", "likely_unregulated"])
def test_filtered_order_is_subsequence_of_unfiltered(all_sites, flt):
    assert _is_subsequence(_ids(_sites(regulation=flt)), _ids(all_sites))


# (4) helper ----------------------------------------------------------------
def test_regulation_levels_constant():
    from climate_core.catalog.regulation import REGULATION_LEVELS

    assert REGULATION_LEVELS == LEVELS
    assert isinstance(REGULATION_LEVELS, tuple)


@pytest.mark.parametrize(
    "name,area,site_no",
    [
        ("NF CLEARWATER RIVER AT AHSAHKA ID", 2443.0, "13341000"),
        ("SOMETHING RESERVOIR NEAR X", 50.0, None),
        ("TINY CREEK NEAR Y", 5.0, None),
        ("BIG RIVER AT Z", 5000.0, None),
        ("BIG RIVER AT Z", None, None),
        (None, None, None),
        ("CREEK BELOW DAM", float("nan"), "99999999"),
        ("", 0.0, None),
    ],
)
def test_regulation_hint_returns_only_valid_levels(name, area, site_no):
    h = regulation_hint(name, area, site_no=site_no)
    assert h.level in LEVELS
    assert isinstance(h.reason, str) and h.reason


# (5) other routes unchanged ------------------------------------------------
def test_siteout_schema_unchanged():
    assert set(schemas.SiteOut.model_fields) == SITE_KEYS


def test_health_has_no_regulation_fields():
    d = client.get("/api/health").json()
    assert not (REG_KEYS & set(d))


def test_snotel_sites_have_no_regulation_fields():
    items = client.get("/api/snotel-sites", params={"limit": 20}).json()
    assert items
    for s in items:
        assert not (REG_KEYS & set(s))
