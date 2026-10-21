"""Locked spec: dynamic default analysis window (api/defaults.py).

Water year runs Oct 1 - Sep 30. The default window is
(1985-10-01, last COMPLETE water year end). "Today" is controlled by
monkeypatching ``api.defaults._today``; the end date must be resolved at call /
validation / request time, never at import time. No network.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from api import defaults, schemas, service
from api.main import app

SITE = "13340000"

# (today, expected last complete water-year end)
BOUNDARY_CASES = [
    (date(2026, 10, 21), date(2026, 9, 30)),
    (date(2026, 10, 1), date(2026, 9, 30)),   # first day after WY2026 ends
    (date(2026, 9, 30), date(2025, 9, 30)),   # WY2026 not complete until Sep 30 has passed
    (date(2026, 9, 29), date(2025, 9, 30)),
    (date(2026, 12, 31), date(2026, 9, 30)),
    (date(2027, 1, 1), date(2026, 9, 30)),    # calendar-year rollover
    (date(2027, 1, 15), date(2026, 9, 30)),
    (date(2027, 10, 1), date(2027, 9, 30)),
    (date(2026, 1, 1), date(2025, 9, 30)),
    (date(2024, 2, 29), date(2023, 9, 30)),   # leap day
    (date(2024, 10, 1), date(2024, 9, 30)),
    (date(2000, 1, 1), date(1999, 9, 30)),
]


def pin_today(monkeypatch, d: date) -> None:
    monkeypatch.setattr("api.defaults._today", lambda: d)


# --------------------------------------------------------------------------- #
# api.defaults
# --------------------------------------------------------------------------- #
def test_default_start_constant():
    assert defaults.DEFAULT_START == date(1985, 10, 1)
    assert type(defaults.DEFAULT_START) is date


def test_today_wrapper_returns_real_date():
    t = defaults._today()
    assert type(t) is date
    assert t == date.today()


@pytest.mark.parametrize("today,expected", BOUNDARY_CASES)
def test_last_complete_water_year_end_explicit_today(today, expected):
    assert defaults.last_complete_water_year_end(today) == expected


@pytest.mark.parametrize("today,expected", BOUNDARY_CASES)
def test_last_complete_water_year_end_uses_patched_today_when_none(monkeypatch, today, expected):
    pin_today(monkeypatch, today)
    assert defaults.last_complete_water_year_end() == expected
    assert defaults.last_complete_water_year_end(None) == expected


def test_explicit_today_overrides_patched_today(monkeypatch):
    pin_today(monkeypatch, date(2030, 6, 1))
    assert defaults.last_complete_water_year_end(date(2026, 10, 21)) == date(2026, 9, 30)


def test_result_is_always_a_past_sep_30_within_a_year():
    d = date(1999, 1, 1)
    one_day = date(2000, 1, 2) - date(2000, 1, 1)
    while d < date(2003, 1, 1):
        end = defaults.last_complete_water_year_end(d)
        assert (end.month, end.day) == (9, 30)
        assert end < d                       # strictly before today
        assert (d - end).days <= 366         # and the most recent such Sep 30
        d += one_day


@pytest.mark.parametrize("today,expected_end", BOUNDARY_CASES)
def test_default_window(monkeypatch, today, expected_end):
    assert defaults.default_window(today) == (date(1985, 10, 1), expected_end)
    pin_today(monkeypatch, today)
    assert defaults.default_window() == (date(1985, 10, 1), expected_end)


def test_default_window_returns_tuple_of_dates():
    s, e = defaults.default_window(date(2026, 10, 21))
    assert type(s) is date and type(e) is date


# --------------------------------------------------------------------------- #
# BaseflowRequest: resolved at validation time
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("today,expected_end", BOUNDARY_CASES)
def test_baseflow_request_omitted_dates_use_defaults(monkeypatch, today, expected_end):
    pin_today(monkeypatch, today)
    r = schemas.BaseflowRequest(site_no=SITE)
    assert r.start_date == date(1985, 10, 1)
    assert r.end_date == expected_end


@pytest.mark.parametrize("kwargs", [
    {"start_date": None},
    {"end_date": None},
    {"start_date": None, "end_date": None},
])
def test_baseflow_request_explicit_null_equals_omitted(monkeypatch, kwargs):
    pin_today(monkeypatch, date(2026, 10, 21))
    r = schemas.BaseflowRequest(site_no=SITE, **kwargs)
    assert (r.start_date, r.end_date) == (date(1985, 10, 1), date(2026, 9, 30))


def test_baseflow_request_null_via_json_validation(monkeypatch):
    pin_today(monkeypatch, date(2026, 10, 21))
    r = schemas.BaseflowRequest.model_validate_json(
        '{"site_no": "13340000", "start_date": null, "end_date": null}'
    )
    assert (r.start_date, r.end_date) == (date(1985, 10, 1), date(2026, 9, 30))


def test_baseflow_request_rolls_over_between_constructions(monkeypatch):
    pin_today(monkeypatch, date(2026, 9, 30))
    first = schemas.BaseflowRequest(site_no=SITE)
    pin_today(monkeypatch, date(2026, 10, 1))
    second = schemas.BaseflowRequest(site_no=SITE)
    assert first.end_date == date(2025, 9, 30)
    assert second.end_date == date(2026, 9, 30)
    # an already-built request is not mutated by later clock changes
    assert first.end_date == date(2025, 9, 30)


def test_baseflow_request_null_also_rolls_over(monkeypatch):
    pin_today(monkeypatch, date(2026, 12, 1))
    a = schemas.BaseflowRequest(site_no=SITE, end_date=None)
    pin_today(monkeypatch, date(2027, 12, 1))
    b = schemas.BaseflowRequest(site_no=SITE, end_date=None)
    assert (a.end_date, b.end_date) == (date(2026, 9, 30), date(2027, 9, 30))


def test_baseflow_request_explicit_dates_preserved(monkeypatch):
    pin_today(monkeypatch, date(2040, 1, 1))
    r = schemas.BaseflowRequest(site_no=SITE, start_date="2000-01-01", end_date="2010-06-15")
    assert (r.start_date, r.end_date) == (date(2000, 1, 1), date(2010, 6, 15))


def test_baseflow_request_explicit_start_with_default_end(monkeypatch):
    pin_today(monkeypatch, date(2026, 10, 21))
    r = schemas.BaseflowRequest(site_no=SITE, start_date="2001-10-01")
    assert (r.start_date, r.end_date) == (date(2001, 10, 1), date(2026, 9, 30))


def test_baseflow_request_explicit_end_with_default_start(monkeypatch):
    pin_today(monkeypatch, date(2026, 10, 21))
    r = schemas.BaseflowRequest(site_no=SITE, end_date="2005-09-30")
    assert (r.start_date, r.end_date) == (date(1985, 10, 1), date(2005, 9, 30))


@pytest.mark.parametrize("start,end", [
    ("2000-10-01", "2000-10-01"),   # equal
    ("2001-10-01", "2000-10-01"),   # reversed
])
def test_baseflow_request_start_not_before_end_rejected(monkeypatch, start, end):
    pin_today(monkeypatch, date(2026, 10, 21))
    with pytest.raises(ValidationError):
        schemas.BaseflowRequest(site_no=SITE, start_date=start, end_date=end)


def test_baseflow_request_explicit_start_after_default_end_rejected(monkeypatch):
    pin_today(monkeypatch, date(2026, 10, 21))
    with pytest.raises(ValidationError):
        schemas.BaseflowRequest(site_no=SITE, start_date="2026-09-30")  # == default end
    with pytest.raises(ValidationError):
        schemas.BaseflowRequest(site_no=SITE, start_date="2027-01-01")


def test_baseflow_request_explicit_end_not_after_default_start_rejected(monkeypatch):
    pin_today(monkeypatch, date(2026, 10, 21))
    with pytest.raises(ValidationError):
        schemas.BaseflowRequest(site_no=SITE, end_date="1985-10-01")
    with pytest.raises(ValidationError):
        schemas.BaseflowRequest(site_no=SITE, end_date="1980-01-01")


# --------------------------------------------------------------------------- #
# Streamflow AnalysisRequest + service consumption
# --------------------------------------------------------------------------- #
def test_analysis_request_start_date_still_none_by_default():
    # end_date resolution is asserted at the service layer below (either schema
    # or service may resolve it). Start stays "start of record" (None).
    r = schemas.AnalysisRequest(site_no=SITE)
    assert r.start_date is None


class _Captured(Exception):
    pass


@pytest.fixture
def fetch_spy(monkeypatch):
    calls: list[tuple] = []

    def fake(site_no, start_date, end_date):
        calls.append((site_no, start_date, end_date))
        return pd.DataFrame({"Date": [], "Discharge": []})  # empty -> service raises ValueError

    monkeypatch.setattr(service, "_fetch_raw", fake)
    return calls


@pytest.mark.parametrize("today,expected_end", [
    (date(2026, 10, 21), "2026-09-30"),
    (date(2026, 9, 30), "2025-09-30"),
    (date(2027, 1, 15), "2026-09-30"),
    (date(2024, 2, 29), "2023-09-30"),
])
@pytest.mark.parametrize("body", [{}, {"end_date": None}])
def test_streamflow_end_date_defaults_to_last_complete_water_year(monkeypatch, fetch_spy, today, expected_end, body):
    pin_today(monkeypatch, today)
    req = schemas.AnalysisRequest(site_no=SITE, **body)
    with pytest.raises(ValueError):  # empty fetch -> "No data returned"
        service.run_analysis(req)
    assert len(fetch_spy) == 1
    site, start, end = fetch_spy[0]
    assert site == SITE
    assert str(end)[:10] == expected_end
    assert str(start)[:10] == "1900-10-01"  # start of record unchanged


def test_streamflow_end_date_not_today(monkeypatch, fetch_spy):
    pin_today(monkeypatch, date(2026, 10, 21))
    with pytest.raises(ValueError):
        service.run_analysis(schemas.AnalysisRequest(site_no=SITE))
    assert str(fetch_spy[0][2])[:10] != date.today().isoformat()


def test_streamflow_explicit_end_date_preserved(monkeypatch, fetch_spy):
    pin_today(monkeypatch, date(2026, 10, 21))
    with pytest.raises(ValueError):
        service.run_analysis(schemas.AnalysisRequest(site_no=SITE, start_date="1990-10-01", end_date="2000-05-05"))
    assert str(fetch_spy[0][1])[:10] == "1990-10-01"
    assert str(fetch_spy[0][2])[:10] == "2000-05-05"


def test_streamflow_end_date_rolls_over_per_call(monkeypatch, fetch_spy):
    req = schemas.AnalysisRequest(site_no=SITE)
    pin_today(monkeypatch, date(2026, 9, 30))
    with pytest.raises(ValueError):
        service.run_analysis(req)
    pin_today(monkeypatch, date(2026, 10, 1))
    with pytest.raises(ValueError):
        service.run_analysis(req)
    assert [str(c[2])[:10] for c in fetch_spy] == ["2025-09-30", "2026-09-30"]


# --------------------------------------------------------------------------- #
# GET /api/defaults
# --------------------------------------------------------------------------- #
client = TestClient(app)


@pytest.fixture
def open_client(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with TestClient(app) as c:
        yield c


def test_defaults_endpoint_shape(open_client, monkeypatch):
    pin_today(monkeypatch, date(2026, 10, 21))
    r = open_client.get("/api/defaults")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.json() == {"start_date": "1985-10-01", "end_date": "2026-09-30"}


@pytest.mark.parametrize("today,expected_end", BOUNDARY_CASES)
def test_defaults_endpoint_end_date_matches_helper(open_client, monkeypatch, today, expected_end):
    pin_today(monkeypatch, today)
    body = open_client.get("/api/defaults").json()
    assert body["start_date"] == "1985-10-01"
    assert body["end_date"] == expected_end.isoformat()
    assert body["end_date"] == defaults.last_complete_water_year_end().isoformat()


def test_defaults_endpoint_resolved_per_request(open_client, monkeypatch):
    pin_today(monkeypatch, date(2026, 9, 30))
    first = open_client.get("/api/defaults").json()
    pin_today(monkeypatch, date(2026, 10, 1))
    second = open_client.get("/api/defaults").json()
    assert first["end_date"] == "2025-09-30"
    assert second["end_date"] == "2026-09-30"


def test_defaults_endpoint_get_only(open_client):
    assert open_client.post("/api/defaults", json={}).status_code == 405


# Auth: every /api route except /api/health is protected by the SSO middleware
# (see tests/test_sso.py); /api/defaults is NOT exempt.
SSO_SECRET = "unit-test-sso-secret-0123456789abcdef"


@pytest.fixture
def secured_client(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", SSO_SECRET)
    with TestClient(app) as c:
        yield c


def test_defaults_endpoint_requires_auth_when_secret_set(secured_client):
    r = secured_client.get("/api/defaults")
    assert r.status_code == 401


def test_defaults_endpoint_allows_streamflow_group(secured_client, monkeypatch):
    import datetime as dt

    import jwt

    pin_today(monkeypatch, date(2026, 10, 21))
    token = jwt.encode(
        {"sub": "u", "groups": ["streamflow"], "exp": dt.datetime.now(dt.timezone.utc) + dt.timedelta(hours=1)},
        SSO_SECRET,
        algorithm="HS256",
    )
    secured_client.cookies.set("streamflows_auth", token)
    r = secured_client.get("/api/defaults")
    assert r.status_code == 200
    assert r.json()["end_date"] == "2026-09-30"
