"""Check a fresh installation without reading the developer's .env or database."""

import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("override_database", [False, True])
def test_dotenv_configuration_and_application_startup(tmp_path, override_database):
    backend = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    for key in (
        "SECRET_KEY",
        "DATABASE_URL",
        "BOOTSTRAP_SUPERADMIN_EMAIL",
        "COOKIE_SECURE",
        "COOKIE_SAMESITE",
    ):
        env.pop(key, None)
    env["PYTHONPATH"] = str(backend)

    database_url = "postgresql://postgres:local-test@localhost:55432/from_dotenv"
    (tmp_path / ".env").write_text(
        "SECRET_KEY=installation-test-key-with-at-least-32-characters\n"
        f"DATABASE_URL={database_url}\n"
        "COOKIE_SECURE=False\n"
        "COOKIE_SAMESITE=lax\n"
    )
    if override_database:
        database_url = "postgresql://postgres:local-test@db:5432/from_environment"
        env["DATABASE_URL"] = database_url

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
import sys
from fastapi.testclient import TestClient
from app.core.config import settings
from app.database import SQLALCHEMY_DATABASE_URL, engine
from app.main import app

assert settings.DATABASE_URL == sys.argv[1]
assert SQLALCHEMY_DATABASE_URL == sys.argv[1]
assert engine.url.render_as_string(hide_password=False) == sys.argv[1]
assert settings.COOKIE_SECURE is False
assert settings.COOKIE_SAMESITE == 'lax'
with TestClient(app) as client:
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
    assert client.get('/openapi.json').status_code == 200
""",
            database_url,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
