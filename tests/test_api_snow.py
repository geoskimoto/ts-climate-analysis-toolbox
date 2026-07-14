"""Snow API tests via TestClient. The /analyze/snow test hits live NRCS."""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health_reports_snotel_count():
    body = client.get("/api/health").json()
    assert body["snotel_sites"] > 400


def test_list_snotel_sites():
    assert len(client.get("/api/snotel-sites?limit=10").json()) == 10
    mt = client.get("/api/snotel-sites?state=MT&limit=5").json()
    assert mt and all(s["state"] == "MT" for s in mt)
    for s in client.get("/api/snotel-sites?limit=20").json():
        assert s["huc"]  # HUC present for future basin pairing


def test_analyze_snow_validation_errors():
    assert client.post("/api/analyze/snow", json={"station_triplet": "999:ZZ:SNTL"}).status_code == 404
    assert (
        client.post("/api/analyze/snow", json={"station_triplet": "302:OR:SNTL", "alpha": 2}).status_code
        == 422
    )


@pytest.mark.network
def test_analyze_snow_full_payload():
    r = client.post(
        "/api/analyze/snow",
        json={
            "station_triplet": "302:OR:SNTL",  # Aneroid Lake, OR
            "start_date": "1985-10-01",
            "end_date": "2020-09-30",
            "alpha": 0.1,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["value_label"] == "SWE"
    assert data["meta"]["n_water_years"] > 25
    assert len(data["climatology"]) >= 365
    assert data["peak_swe"]["points"]
    assert data["april1_swe"]["mk"]["trend"] in {"increasing", "decreasing", "no trend"}
    assert data["hydrograph"] and len(data["hydrograph"]) == data["meta"]["n_water_years"]
