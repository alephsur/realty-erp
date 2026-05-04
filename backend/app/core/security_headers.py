"""Security headers middleware for FastAPI.

Adds the following headers to every HTTP response:
  - Strict-Transport-Security  (HSTS)
  - X-Content-Type-Options
  - X-Frame-Options
  - Referrer-Policy
  - Permissions-Policy
  - Content-Security-Policy    (value driven by settings.CSP_POLICY)

Register it in main.py *after* CORSMiddleware so it runs on every response,
including CORS pre-flight responses.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from app.core.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response: Response = await call_next(request)

        # Prevent browsers from sniffing the content-type
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Deny framing — blocks clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Enforce HTTPS for 1 year, include sub-domains
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )

        # Limit the Referer header to same-origin
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Disable browser features we don't need
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), payment=()"
        )

        # Content-Security-Policy (value from settings, fully configurable)
        response.headers["Content-Security-Policy"] = settings.CSP_POLICY

        return response
