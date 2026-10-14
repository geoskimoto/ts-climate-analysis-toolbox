"""Tests for the curated regulated-gauge list.

Spec: docs/regulated_gauges_plan.md (sole contract). Structural data checks read
the CSV with pandas directly (not through the loader). Loader validation tests
point ``climate_core.catalog.regulation._REGULATED_PATH`` (a pathlib.Path; naming
assumption, same convention as ``_CATALOG_PATH``) at crafted temp CSVs and clear
the lru_cache of ``regulated_gauges``. No network; synthetic seeded data only.
"""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path

import pandas as pd
import pytest

from api import schemas, service
from api.service_baseflow import run_baseflow_analysis
from climate_core.catalog import default_catalog
from climate_core.catalog import regulation as reg
from climate_core.catalog.regulation import RegulationHint, regulation_hint

from tests.test_service_baseflow import FakeFetch, make_daily



class _Lazy:
    """Resolve ``regulated_gauges`` at call time so the file collects before it exists."""

    def __call__(self):
        return reg.regulated_gauges()

    def cache_clear(self):
        reg.regulated_gauges.cache_clear()


regulated_gauges = _Lazy()
DATA_PATH = Path(reg.__file__).parent / "data" / "regulated_gauges.csv"
COLUMNS = ["site_no", "name", "regulator", "kind", "confidence", "source_url"]
KINDS = {"dam_release", "diversion", "reservoir_storage", "canal_or_return_flow", "multiple"}
CONFIDENCES = {"high", "medium"}
ANCHORS = ["13340000", "14105700", "13290450", "13206000"]
HTTP = re.compile(r"^https?://\S+$")


# --------------------------------------------------------------------------- #
# (1) Data-file integrity (plain pandas, not the loader)
# --------------------------------------------------------------------------- #
@pytest.fixture(scope="module")
def raw() -> pd.DataFrame:
    return pd.read_csv(DATA_PATH, dtype=str, keep_default_na=False, encoding="utf-8")


def test_data_file_exists():
    assert DATA_PATH.is_file()


def test_required_columns(raw):
    assert set(COLUMNS) <= set(raw.columns)


def test_site_no_unique(raw):
    dup = raw["site_no"][raw["site_no"].duplicated()].tolist()
    assert not dup, f"duplicate site_no: {dup}"


def test_every_site_in_catalog(raw):
    cat = default_catalog()
    missing = []
    for s in raw["site_no"]:
        try:
            cat.get(s)
        except Exception:  # noqa: BLE001 - any lookup failure means not in catalog
            missing.append(s)
    assert not missing, f"not in default_catalog(): {missing}"


def test_name_equals_catalog_name(raw):
    cat = default_catalog()
    bad = [(r.site_no, r.name, cat.get(r.site_no).name) for r in raw.itertuples() if r.name != cat.get(r.site_no).name]
    assert not bad, bad


def test_kind_and_confidence_allowed(raw):
    assert set(raw["kind"]) <= KINDS, set(raw["kind"]) - KINDS
    assert set(raw["confidence"]) <= CONFIDENCES, set(raw["confidence"]) - CONFIDENCES


def test_regulator_non_empty(raw):
    assert (raw["regulator"].str.strip() != "").all()


def test_high_confidence_requires_http_source(raw):
    high = raw[raw["confidence"] == "high"]
    assert len(high) > 0
    bad = high[~high["source_url"].str.strip().str.match(HTTP)]
    assert bad.empty, bad["site_no"].tolist()


def test_any_non_blank_source_url_is_http(raw):
    nb = raw[raw["source_url"].str.strip() != ""]
    bad = nb[~nb["source_url"].str.strip().str.match(HTTP)]
    assert bad.empty, bad["site_no"].tolist()


@pytest.mark.parametrize("site_no", ANCHORS)
def test_anchor_present(raw, site_no):
    assert site_no in set(raw["site_no"])


def test_size_sanity(raw):
    assert 40 <= len(raw) <= 400


# --------------------------------------------------------------------------- #
# (2) Loader
# --------------------------------------------------------------------------- #
def test_loader_returns_dict_keyed_by_site_no(raw):
    g = regulated_gauges()
    assert isinstance(g, dict)
    assert set(g) == set(raw["site_no"])
    for k, v in g.items():
        assert isinstance(v, reg.RegulatedGauge)
        assert v.site_no == k


def test_regulated_gauge_frozen_dataclass_fields():
    assert dataclasses.is_dataclass(reg.RegulatedGauge)
    assert [f.name for f in dataclasses.fields(reg.RegulatedGauge)] == COLUMNS
    g = regulated_gauges()["13340000"]
    with pytest.raises(dataclasses.FrozenInstanceError):
        g.regulator = "x"  # type: ignore[misc]
    assert "Dworshak" in g.regulator
    assert g.kind in KINDS and g.confidence in CONFIDENCES


def test_loader_is_cached():
    assert regulated_gauges() is regulated_gauges()


GOOD = ["13340000", "Clearwater R", "Dworshak Dam", "dam_release", "high", "https://example.org/x"]


def _csv(tmp_path, rows, header=COLUMNS):
    p = tmp_path / "rg.csv"
    lines = [",".join(header)] + [",".join(r) for r in rows]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def load_from(tmp_path):
    """Return f(rows, header=...) -> loader result using a crafted CSV; restores state."""
    original = reg._REGULATED_PATH

    def _load(rows, header=COLUMNS):
        reg._REGULATED_PATH = _csv(tmp_path, rows, header)
        regulated_gauges.cache_clear()
        return regulated_gauges()

    yield _load
    reg._REGULATED_PATH = original
    regulated_gauges.cache_clear()


def _row(**kw):
    d = dict(zip(COLUMNS, GOOD))
    d.update(kw)
    return [d[c] for c in COLUMNS]


def test_crafted_valid_csv_loads(load_from):
    g = load_from([_row(), _row(site_no="14105700", confidence="medium", source_url="")])
    assert set(g) == {"13340000", "14105700"}
    assert g["14105700"].source_url in ("", None)


def test_missing_required_column(load_from):
    hdr = [c for c in COLUMNS if c != "kind"]
    rows = [[v for c, v in zip(COLUMNS, GOOD) if c != "kind"]]
    with pytest.raises(ValueError, match="kind"):
        load_from(rows, header=hdr)


def test_duplicate_site_no(load_from):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(), _row()])


def test_bad_kind(load_from):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(kind="bogus")])


def test_bad_confidence(load_from):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(confidence="low")])


def test_empty_regulator(load_from):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(regulator="")])


def test_high_without_source_url(load_from):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(source_url="")])


def test_high_with_non_http_source_url(load_from):
    with pytest.raises(ValueError, match="13340000"):
        load_from([_row(source_url="ftp://example.org/x")])


def test_error_names_offending_row_not_others(load_from):
    with pytest.raises(ValueError) as ei:
        load_from([_row(), _row(site_no="14105700", kind="bogus")])
    assert "14105700" in str(ei.value)


# --------------------------------------------------------------------------- #
# (3) regulation_hint precedence
# --------------------------------------------------------------------------- #
SPREAD = [
    ("SNAKE RIVER BELOW X", 10),
    ("PLAIN CR", 10),
    ("PLAIN CR", 5000),
    ("COLUMBIA RIVER AT GRAND COULEE DAM", 74000),
    ("CLEARWATER RIVER AT OROFINO ID", 5507),
    (None, None),
    ("", float("nan")),
]


def test_curated_beats_nonmatching_name_and_small_area():
    h = regulation_hint("PLAIN CR", 10, site_no="13340000")
    assert h.level == "regulated"


def test_curated_beats_below_pattern_name():
    h = regulation_hint("SNAKE RIVER BELOW HELLS CANYON", 5000, site_no="13340000")
    assert h.level == "regulated"
    assert "Station name contains" not in h.reason


def test_reason_format():
    g = regulated_gauges()["13340000"]
    h = regulation_hint("anything", 1.0, site_no="13340000")
    assert isinstance(h, RegulationHint)
    assert h.reason == f"Known regulation: {g.regulator} ({g.kind}, {g.confidence} confidence; curated list)."


@pytest.mark.parametrize("name, area", SPREAD)
def test_no_site_no_unchanged(name, area):
    assert regulation_hint(name, area, site_no=None) == regulation_hint(name, area)
    assert regulation_hint(name, area).level != "regulated"


@pytest.mark.parametrize("name, area", SPREAD)
def test_unlisted_site_no_unchanged(name, area):
    assert "00000000" not in regulated_gauges()
    assert regulation_hint(name, area, site_no="00000000") == regulation_hint(name, area)


# --------------------------------------------------------------------------- #
# (4) Service / API
# --------------------------------------------------------------------------- #
@pytest.fixture
def fetch(monkeypatch):
    f = FakeFetch(make_daily())
    monkeypatch.setattr(service, "_fetch_raw", f)
    return f


def _analysis(site_no):
    res = run_baseflow_analysis(schemas.BaseflowRequest(site_no=site_no))
    return res.model_dump()


def test_service_curated_site_is_regulated(fetch):
    r = _analysis("13340000")["meta"]["regulation"]
    assert r["level"] == "regulated"
    assert "Dworshak" in r["reason"]


def test_service_unlisted_catalog_site_not_regulated_level(fetch):
    listed = set(regulated_gauges())
    site = next(s.site_no for s in default_catalog().all() if s.site_no not in listed)
    r = _analysis(site)["meta"]["regulation"]
    assert r["level"] in {"likely_regulated", "likely_unregulated", "unknown"}
