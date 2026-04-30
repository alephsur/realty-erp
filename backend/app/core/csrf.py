"""CSRF protection — double-submit cookie pattern.

Strategy
--------
On login the backend emits two cookies:
  1. ``access_token``  – httpOnly, SameSite=Strict  (JWT, invisible to JS)
  2. ``csrf_token``    – SameSite=Strict, NOT httpOnly  (JS can read it)

For every state-mutating request (POST / PUT / PATCH / DELETE) the frontend
must read ``csrf_token`` from ``document.cookie`` and send it as the
``X-CSRF-Token`` request header.

``verify_csrf_token`` is a FastAPI dependency that:
  - Does nothing for safe methods (GET, HEAD, OPTIONS)
  - For unsafe methods: compares the cookie value with the header value
    using a constant-time comparison to prevent timing attacks
  - Returns 403 if they are absent or do not match
"""
import secrets

from fastapi import Depends, HTTPException, Request, status

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
CSRF_HEADER = "X-CSRF-Token"
CSRF_COOKIE = "csrf_token"


def verify_csrf_token(request: Request) -> None:
    """FastAPI dependency — inject in any router or individual route."""
    if request.method in SAFE_METHODS:
        return  # CSRF not relevant for read-only requests

    cookie_token: str | None = request.cookies.get(CSRF_COOKIE)
    header_token: str | None = request.headers.get(CSRF_HEADER)

    if not cookie_token or not header_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing",
        )

    # secrets.compare_digest prevents timing-oracle attacks
    if not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token mismatch",
        )
