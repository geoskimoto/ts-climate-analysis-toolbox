"""API tests via FastAPI TestClient.

Catalog-only routes run offline; the /analyze test hits live USGS and is marked
'network'.
"""

import pytest
from fastapi.testclient import TestClient

from api.main import app

client = TestClient(app)


def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert r.json()["sites"] > 800


def test_list_sites_default_and_filtered():
    assert len(client.get("/api/sites?limit=10").json()) == 10
    wa = client.get("/api/sites?state=WA&limit=5").json()
    assert wa and all(s["state"] == "WA" for s in wa)
    # basin should be free of the stray non-breaking space.
    for s in client.get("/api/sites?limit=50").json():
        assert not s["basin"].startswith(" ") and "\xa0" not in s["basin"]


def test_get_site_and_404():
    r = client.get("/api/sites/13340000")
    assert r.status_code == 200
    assert "CLEARWATER" in r.json()["name"].upper()
    assert client.get("/api/sites/00000000").status_code == 404


def test_analyze_validation_errors():
    # site not in catalog -> 404
    assert client.post("/api/analyze", json={"site_no": "00000000"}).status_code == 404
    # out-of-range threshold -> 422 (pydantic)
    assert (
        client.post("/api/analyze", json={"site_no": "13340000", "threshold_percent": 1.5}).status_code
        == 422
    )


@pytest.mark.network
def test_analyze_full_payload():
    r = client.post(
        "/api/analyze",
        json={
            "site_no": "13340000",
            "start_date": "1960-10-01",
            "end_date": "2020-09-30",
            "alpha": 0.1,
        },
    )
    assert r.status_code == 200
    data = r.json()
    assert data["meta"]["n_water_years"] > 40
    assert len(data["climatology"]) >= 365
    assert data["center_of_timing"]["mk_timing"]["trend"] in {
        "increasing",
        "decreasing",
        "no trend",
    }
    assert len(data["seasonal_volumes"]) == 4
    assert data["hydrograph"] and len(data["hydrograph"]) == data["meta"]["n_water_years"]


@pytest.mark.network
def test_analyze_incomplete_range_returns_422():
    r = client.post(
        "/api/analyze",
        json={"site_no": "13340000", "start_date": "2020-01-01", "end_date": "2020-03-01"},
    )
    assert r.status_code == 422
