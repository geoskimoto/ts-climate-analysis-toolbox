"""SSO middleware for the streamflows.org portal JWT.

FastAPI port of the ``streamflows_auth`` Flask middleware: validates the
``streamflows_auth`` HS256 cookie signed with ``JWT_SECRET`` and requires the
"streamflow" group ("admin" bypasses). The Flask middleware exempts ``/api/``
paths because in the Dash apps those are internal routes; here the entire data
surface IS ``/api/``, so every route is protected except ``/api/health``.
Errors are JSON (401/403) rather than login redirects because callers are
``fetch()`` requests from the SPA — the page itself is gated by nginx
``auth_request`` against ``GET /api/auth/verify``.

``JWT_SECRET`` is read from the environment at request time; when it is unset
(local dev, offline test suite) auth is disabled and the app runs open.
"""

from __future__ import annotations

import os

import jwt
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

COOKIE_NAME = "streamflows_auth"
REQUIRED_GROUP = "streamflow"
ADMIN_GROUP = "admin"
_EXEMPT_PATHS = ("/api/health", "/api/auth/verify")


def _authorize(request: Request, secret: str) -> Response | None:
    """Return a 401/403 response, or None if the request is authorized."""
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return JSONResponse({"detail": "Not authenticated."}, status_code=401)
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return JSONResponse({"detail": "Invalid or expired token."}, status_code=401)

    groups = payload.get("groups", [])
    if REQUIRED_GROUP not in groups and ADMIN_GROUP not in groups:
        return JSONResponse({"detail": "Insufficient permissions."}, status_code=403)

    request.state.current_user = payload.get("sub", "")
    return None


def install_auth(app: FastAPI) -> None:
    @app.get("/api/auth/verify", include_in_schema=False)
    def verify(request: Request) -> Response:
        """nginx auth_request endpoint: 204 authorized, 401/403 otherwise."""
        secret = os.environ.get("JWT_SECRET")
        if secret:
            error = _authorize(request, secret)
            if error is not None:
                return error
        return Response(status_code=204)

    @app.middleware("http")
    async def _sso_middleware(request: Request, call_next):
        secret = os.environ.get("JWT_SECRET")
        if secret and request.url.path not in _EXEMPT_PATHS:
            error = _authorize(request, secret)
            if error is not None:
                return error
        return await call_next(request)
