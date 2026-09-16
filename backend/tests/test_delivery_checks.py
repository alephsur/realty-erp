"""The delivery gate must reject incomplete reports and unsafe E2E fixture targets."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "report,expected",
    [
        ('<testsuites><testsuite><testcase name="flow"/></testsuite></testsuites>', 0),
        ('<testsuite><testcase name="flow"><failure/></testcase></testsuite>', 1),
        ('<testsuite><testcase name="flow"><error/></testcase></testsuite>', 1),
        ('<testsuite><testcase name="flow"><skipped/></testcase></testsuite>', 1),
        ("<testsuite/>", 1),
        ("not XML", 1),
        (None, 1),
    ],
)
def test_delivery_gate_exit_code(tmp_path, report, expected):
    path = tmp_path / "results.xml"
    if report is not None:
        path.write_text(report)
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/check_test_results.py"), str(path)],
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == expected, result.stdout + result.stderr


@pytest.mark.parametrize("name", ["production", "realty_e2e_different", ""])
def test_seed_refuses_an_unmanaged_database_before_connecting(tmp_path, name):
    env = {
        **os.environ,
        "PYTHONPATH": str(ROOT / "backend"),
        "DATABASE_URL": "postgresql://unused:unused@127.0.0.1:1/production",
        "SECRET_KEY": "test-only-secret-with-at-least-32-characters",
        "BOOTSTRAP_SUPERADMIN_EMAIL": "",
        "E2E_DATABASE_NAME": name,
        "E2E_SEED_PATH": str(tmp_path / "seed.json"),
    }
    result = subprocess.run(
        [sys.executable, "-m", "scripts.seed_e2e"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode != 0
    assert "Fixtures require the disposable database" in result.stderr
    assert not (tmp_path / "seed.json").exists()
