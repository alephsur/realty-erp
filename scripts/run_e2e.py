#!/usr/bin/env python3
"""Run real-browser checks against an isolated API, build and disposable PostgreSQL."""

import json
import os
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"


def run(command, *, cwd=ROOT, env=None, **kwargs):
    return subprocess.run(command, cwd=cwd, env=env, check=True, timeout=300, **kwargs)


def unused_ports():
    # Hold both sockets until both ports have been allocated.
    with socket.socket() as api, socket.socket() as ui:
        api.bind(("127.0.0.1", 0))
        ui.bind(("127.0.0.1", 0))
        return api.getsockname()[1], ui.getsockname()[1]


def wait_http(url, process):
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Server exited before becoming ready: {url}")
        try:
            with urllib.request.urlopen(url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, TimeoutError):
            time.sleep(0.2)
    raise RuntimeError(f"Server readiness timed out: {url}")


def main():
    run_id = uuid4().hex[:12]
    database = f"realty_e2e_{run_id}"
    container = f"realty-e2e-{run_id}"
    artifacts = FRONTEND / "e2e-artifacts" / run_id
    artifacts.mkdir(parents=True)
    processes = []
    logs = []
    started = False
    print(f"E2E artifacts: {artifacts}", flush=True)

    def interrupted(signum, _frame):
        raise KeyboardInterrupt(f"Signal {signum}")

    old_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        with tempfile.TemporaryDirectory(prefix="realty-e2e-") as temporary:
            work = Path(temporary)
            api_port, ui_port = unused_ports()
            api_url = f"http://127.0.0.1:{api_port}"
            ui_url = f"http://127.0.0.1:{ui_port}"
            password = secrets.token_hex(24)
            # Never accept an existing DATABASE_URL or a server already running.
            run(
                [
                    "docker",
                    "run",
                    "--detach",
                    "--name",
                    container,
                    "--env",
                    f"POSTGRES_PASSWORD={password}",
                    "--env",
                    f"POSTGRES_DB={database}",
                    "--publish",
                    "127.0.0.1::5432",
                    "postgres:15-alpine",
                ],
                capture_output=True,
            )
            started = True
            port = (
                run(
                    ["docker", "port", container, "5432"],
                    capture_output=True,
                    text=True,
                )
                .stdout.strip()
                .rsplit(":", 1)[1]
            )
            for attempt in range(100):
                ready = subprocess.run(
                    [
                        "docker",
                        "exec",
                        container,
                        "pg_isready",
                        "--host",
                        "127.0.0.1",
                        "-U",
                        "postgres",
                        "-d",
                        database,
                    ],
                    capture_output=True,
                    timeout=5,
                )
                if ready.returncode == 0:
                    break
                if attempt == 99:
                    raise RuntimeError("Disposable PostgreSQL did not become ready")
                time.sleep(0.2)
            env = {
                **os.environ,
                "DATABASE_URL": f"postgresql://postgres:{password}@127.0.0.1:{port}/{database}",
                "SECRET_KEY": secrets.token_hex(32),
                "BOOTSTRAP_SUPERADMIN_EMAIL": "",
                "COOKIE_SECURE": "False",
                "COOKIE_SAMESITE": "strict",
                "CORS_ORIGINS": ui_url,
                "FRONTEND_URL": ui_url,
                "VITE_API_URL": api_url,
                "E2E_BASE_URL": ui_url,
                "E2E_API_URL": api_url,
                "E2E_DATABASE_NAME": database,
                "E2E_SEED_PATH": str(work / "seed.json"),
                "E2E_ARTIFACTS_DIR": str(artifacts),
                "UV_PROJECT_ENVIRONMENT": os.environ.get(
                    "UV_PROJECT_ENVIRONMENT", str(work / "venv")
                ),
            }
            uv = ["uv", "run", "--locked", "--python", "3.12"]
            run([*uv, "alembic", "upgrade", "head"], cwd=BACKEND, env=env)
            run([*uv, "python", "-m", "scripts.seed_e2e"], cwd=BACKEND, env=env)
            run(
                ["npm", "run", "build", "--", "--outDir", str(work / "site")],
                cwd=FRONTEND,
                env=env,
            )
            for name, command, cwd, health in [
                (
                    "backend",
                    [
                        *uv,
                        "uvicorn",
                        "app.main:app",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(api_port),
                    ],
                    BACKEND,
                    api_url + "/health",
                ),
                (
                    "frontend",
                    [
                        "npm",
                        "run",
                        "preview",
                        "--",
                        "--host",
                        "127.0.0.1",
                        "--port",
                        str(ui_port),
                        "--strictPort",
                        "--outDir",
                        str(work / "site"),
                    ],
                    FRONTEND,
                    ui_url,
                ),
            ]:
                log = (artifacts / f"{name}.log").open("w")
                logs.append(log)
                process = subprocess.Popen(
                    command,
                    cwd=cwd,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                processes.append(process)
                wait_http(health, process)
            browser_tests = subprocess.Popen(
                ["npx", "--no-install", "playwright", "test", *sys.argv[1:]],
                cwd=FRONTEND,
                env=env,
                start_new_session=True,
            )
            processes.append(browser_tests)
            result_code = browser_tests.wait(timeout=600)
            # Require at least one executed test and reject skips/flakes as a valid delivery.
            report = artifacts / "results.json"
            if result_code:
                return result_code
            if not report.exists():
                raise RuntimeError("Missing browser test results")
            stats = json.loads(report.read_text())["stats"]
            if (
                not stats["expected"]
                or stats["unexpected"]
                or stats["skipped"]
                or stats["flaky"]
            ):
                raise RuntimeError(f"Incomplete browser checks: {stats}")
            return 0
    finally:
        for process in reversed(processes):
            if process.poll() is None:
                with suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    with suppress(ProcessLookupError):
                        os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        for log in logs:
            log.close()
        if started:
            subprocess.run(
                ["docker", "rm", "--force", "--volumes", container],
                capture_output=True,
                timeout=30,
                check=True,
            )
        signal.signal(signal.SIGTERM, old_handler)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, subprocess.SubprocessError, OSError) as error:
        print(f"E2E failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error
