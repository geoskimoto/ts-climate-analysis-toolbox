"""Pairing suggestion and paired snow<->streamflow analysis tests."""

import pytest
from fastapi.testclient import TestClient

from api.main import app
from climate_core.pairing import suggest_snotel_for_gage

client = TestClient(app)


# --- pairing suggestion (offline) ------------------------------------------ #
def test_suggest_returns_ranked_candidates():
    cands = suggest_snotel_for_gage("13340000", max_candidates=5)  # Clearwater at Orofino
    assert cands
    # Same-HUC8 candidates rank ahead of nearby-only ones.
    first_nearby = next((i for i, c in enumerate(cands) if not c.same_huc8), len(cands))
    last_huc = max((i for i, c in enumerate(cands) if c.same_huc8), default=-1)
    assert last_huc < first_nearby
    # Higher-than-gage filter (default) holds.
    for c in cands:
        if c.elevation_diff_ft is not None:
            assert c.elevation_diff_ft > 0


def test_suggest_unknown_gage_raises():
    with pytest.raises(KeyError):
        suggest_snotel_for_gage("00000000")


def test_candidates_endpoint():
    r = client.get("/api/sites/13340000/snotel-candidates?limit=3")
    assert r.status_code == 200
    data = r.json()
    assert data and all("distance_miles" in c and "same_huc8" in c for c in data)
    assert client.get("/api/sites/00000000/snotel-candidates").status_code == 404


def test_paired_validation_errors():
    # unknown gage / station -> 404
    assert client.post(
        "/api/analyze/paired", json={"site_no": "00000000", "station_triplet": "302:OR:SNTL"}
    ).status_code == 404


# --- paired analysis (live) ------------------------------------------------ #
@pytest.mark.network
def test_paired_co_registration_and_corroboration():
    r = client.post(
        "/api/analyze/paired",
        json={"site_no": "13331500", "station_triplet": "523:OR:SNTL", "alpha": 0.1},
    )
    assert r.status_code == 200
    d = r.json()
    w = d["window"]
    # Common window is the intersection -> bounded by the shorter (SNOTEL) record.
    assert w["n_water_years"] >= 10
    assert w["start_water_year"] >= 1978
    # Both domains reported, all series share the common-window length.
    assert len(d["snow_trends"]) == 2 and len(d["streamflow_trends"]) == 2
    for t in d["snow_trends"] + d["streamflow_trends"]:
        assert len(t["points"]) == w["n_water_years"]
    assert d["corroboration"]["category"] in {"corroborating", "mixed", "inconclusive"}


@pytest.mark.network
def test_paired_insufficient_overlap_returns_422():
    # A very recent SNOTEL vs an old gage but a tiny date box -> too little overlap.
    r = client.post(
        "/api/analyze/paired",
        json={
            "site_no": "13331500", "station_triplet": "523:OR:SNTL",
            "start_date": "2020-10-01", "end_date": "2022-09-30",
        },
    )
    assert r.status_code == 422
