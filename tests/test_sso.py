"""Tests for the SSO auth middleware (to be implemented in api/auth.py).

Written test-first: these define the specification and are expected to fail
until the middleware exists.

Spec under test
---------------
- JWT read from cookie ``streamflows_auth`` (HS256, secret from env var
  ``JWT_SECRET`` read at *request* time).
- If ``JWT_SECRET`` is unset, auth is disabled and every route is open.
- When set:
    * ``GET /api/health`` is always open (liveness).
    * ``GET /api/auth/verify`` (for nginx auth_request): 204 valid+allowed,
      401 missing/expired/invalid token, 403 valid token but bad group.
    * All other routes: 401 / 403 JSON (with a ``detail`` key) as above;
      normal behavior when groups include "streamflow" or "admin".

All tests are offline (catalog-backed endpoints only). JWT_SECRET is managed
exclusively via monkeypatch so it never leaks into other test modules.
"""

import datetime as dt

import jwt
import pytest
from fastapi.testclient import TestClient

from api.main import app

TEST_SECRET = "unit-test-sso-secret-0123456789abcdef"  # >=32 bytes for HS256
COOKIE_NAME = "streamflows_auth"


def make_token(groups, exp_delta=dt.timedelta(hours=1), secret=TEST_SECRET, sub="testuser"):
    """Sign an HS256 JWT with the given groups and expiry offset from now."""
    payload = {
        "sub": sub,
        "groups": groups,
        "exp": dt.datetime.now(dt.timezone.utc) + exp_delta,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


@pytest.fixture
def open_client(monkeypatch):
    """Client with JWT_SECRET guaranteed absent -> auth disabled."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with TestClient(app) as c:
        yield c


@pytest.fixture
def client(monkeypatch):
    """Client with JWT_SECRET set -> auth enforced."""
    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    with TestClient(app) as c:
        yield c


def _with_cookie(client, token):
    client.cookies.set(COOKIE_NAME, token)
    return client


# ---------------------------------------------------------------------------
# 1. Auth disabled when JWT_SECRET is not set
# ---------------------------------------------------------------------------


def test_no_secret_auth_disabled_sites_open(open_client):
    r = open_client.get("/api/sites?limit=1")
    assert r.status_code == 200


def test_no_secret_verify_absent_or_open(open_client):
    # With auth disabled the app behaves as it does today; /api/sites must be
    # reachable without any token. (Whether /api/auth/verify exists in this
    # mode is unspecified; the protected-route behavior is the contract.)
    r = open_client.get("/api/sites/13340000")
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 2-3. Secret set: missing cookie rejected, health stays open
# ---------------------------------------------------------------------------


def test_missing_cookie_returns_401(client):
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_health_open_without_cookie(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# 4-6. Group authorization on a protected route
# ---------------------------------------------------------------------------


def test_streamflow_group_allowed(client):
    _with_cookie(client, make_token(["streamflow"]))
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 200
    assert len(r.json()) == 1


def test_admin_group_bypasses_group_requirement(client):
    _with_cookie(client, make_token(["admin"]))
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 200


def test_wrong_group_returns_403(client):
    _with_cookie(client, make_token(["econ"]))
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 403
    assert "detail" in r.json()


def test_post_route_also_protected(client):
    # POST /api/analyze without a token must 401 before the handler runs.
    # A catalog-miss site number keeps this offline pre-implementation
    # (404 today, 401 once the middleware exists).
    r = client.post("/api/analyze", json={"site_no": "00000000"})
    assert r.status_code == 401
    assert "detail" in r.json()


# ---------------------------------------------------------------------------
# 7-9. Invalid tokens
# ---------------------------------------------------------------------------


def test_expired_token_returns_401(client):
    _with_cookie(client, make_token(["streamflow"], exp_delta=dt.timedelta(hours=-1)))
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_garbage_token_returns_401(client):
    _with_cookie(client, "not.a.jwt")
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 401
    assert "detail" in r.json()


def test_wrong_signing_secret_returns_401(client):
    _with_cookie(client, make_token(["streamflow"], secret="a-completely-different-secret-value-xyz"))
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 401
    assert "detail" in r.json()


# ---------------------------------------------------------------------------
# 10. /api/auth/verify (nginx auth_request endpoint)
# ---------------------------------------------------------------------------


def test_verify_no_cookie_401(client):
    r = client.get("/api/auth/verify")
    assert r.status_code == 401


def test_verify_valid_streamflow_token_204(client):
    _with_cookie(client, make_token(["streamflow"]))
    r = client.get("/api/auth/verify")
    assert r.status_code == 204
    assert r.content == b""


def test_verify_admin_token_204(client):
    _with_cookie(client, make_token(["admin"]))
    r = client.get("/api/auth/verify")
    assert r.status_code == 204


def test_verify_wrong_group_403(client):
    _with_cookie(client, make_token(["econ"]))
    r = client.get("/api/auth/verify")
    assert r.status_code == 403


def test_verify_expired_token_401(client):
    _with_cookie(client, make_token(["streamflow"], exp_delta=dt.timedelta(minutes=-5)))
    r = client.get("/api/auth/verify")
    assert r.status_code == 401


# ---------------------------------------------------------------------------
# 11. Error bodies are JSON with a "detail" key
# ---------------------------------------------------------------------------


def test_401_body_is_json_with_detail(client):
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert isinstance(body, dict) and "detail" in body


def test_403_body_is_json_with_detail(client):
    _with_cookie(client, make_token(["econ"]))
    r = client.get("/api/sites?limit=1")
    assert r.status_code == 403
    assert r.headers["content-type"].startswith("application/json")
    body = r.json()
    assert isinstance(body, dict) and "detail" in body


# ---------------------------------------------------------------------------
# Secret is read at request time, not import time
# ---------------------------------------------------------------------------


def test_secret_read_at_request_time(monkeypatch):
    """The same app object must flip between open and enforced as the env
    var changes -- proving the secret is read per-request, not at import."""
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with TestClient(app) as c:
        assert c.get("/api/sites?limit=1").status_code == 200

    monkeypatch.setenv("JWT_SECRET", TEST_SECRET)
    with TestClient(app) as c:
        assert c.get("/api/sites?limit=1").status_code == 401
