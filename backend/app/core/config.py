from __future__ import annotations

from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ------------------------------------------------------------------ #
    # Security — REQUIRED: MUST be set via environment variable.
    # The application will refuse to start if SECRET_KEY is not provided.
    # Generate a strong key with:  python -m secrets (or openssl rand -hex 32)
    # ------------------------------------------------------------------ #
    SECRET_KEY: str  # No default — raises ValidationError at startup if missing

    # ------------------------------------------------------------------ #
    # Bootstrap superadmin — OPTIONAL.
    # Set this env var to trigger automatic superadmin creation on first
    # startup. Leave unset in development to skip bootstrap entirely.
    # The created account will be flagged must_change_password=True so the
    # operator is forced to rotate the temporary password on first login.
    # ------------------------------------------------------------------ #
    BOOTSTRAP_SUPERADMIN_EMAIL: Optional[str] = None

    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # ------------------------------------------------------------------ #
    # CORS — comma-separated list of allowed origins.
    # Example env value:  https://app.mi-inmobiliaria.com,https://admin.mi-inmobiliaria.com
    # ------------------------------------------------------------------ #
    CORS_ORIGINS: str = "http://localhost:5173"

    # ------------------------------------------------------------------ #
    # Cookie security settings.
    # Set COOKIE_SECURE=False in local HTTP development (.env).
    # In production (HTTPS) always keep True.
    # ------------------------------------------------------------------ #
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "strict"

    # ------------------------------------------------------------------ #
    # Content-Security-Policy header value.
    # Override via CSP_POLICY env var to customise per-environment.
    # ------------------------------------------------------------------ #
    CSP_POLICY: str = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )

    @field_validator("SECRET_KEY")
    @classmethod
    def secret_key_must_not_be_empty(cls, v: str) -> str:
        if not v or len(v) < 32:
            raise ValueError(
                "SECRET_KEY must be set via environment variable and be at least "
                "32 characters long. Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        return v

    def get_cors_origins(self) -> List[str]:
        """Return parsed list of allowed CORS origins."""
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    class Config:
        case_sensitive = True
        env_file = ".env"


settings = Settings()
