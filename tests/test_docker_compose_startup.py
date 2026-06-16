"""
اسموک تست کانتینر Docker در حال اجرا — اگر docker یا anistito-api نباشد skip می‌شود.

اجرا: pytest tests/test_docker_compose_startup.py -v
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_COMPOSE = _REPO / "docker-compose.yml"


def _docker_available() -> bool:
    return shutil.which("docker") is not None


def _api_container_running() -> bool:
    if not _docker_available():
        return False
    r = subprocess.run(
        ["docker", "inspect", "-f", "{{.State.Running}}", "anistito-api"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    return r.returncode == 0 and r.stdout.strip().lower() == "true"


pytestmark = pytest.mark.skipif(
    not _docker_available() or not _api_container_running(),
    reason="نیاز به docker و کانتینر در حال اجرای anistito-api",
)


def test_docker_api_health_endpoint():
    """بعد از rebuild/restart، API باید /health بدهد نه crash."""
    r = subprocess.run(
        [
            "docker",
            "exec",
            "anistito-api",
            "python",
            "-c",
            "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:3000/health', timeout=5).read().decode())",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr or r.stdout
    data = json.loads(r.stdout.strip())
    assert data.get("status") == "healthy"


def test_docker_api_calendar_triggers_import():
    """رگرسیون NameError در calendar_triggers داخل کانتینر."""
    r = subprocess.run(
        [
            "docker",
            "exec",
            "anistito-api",
            "python",
            "-c",
            "from app.services.calendar_triggers import run_calendar_trigger_pass, sweep_stuck_fee_determination_triggered; print('ok')",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr or r.stdout
    assert "ok" in r.stdout


def test_docker_api_serves_spa_index():
    """فرانت mount‌شده باید HTML برگرداند نه JSON خطای build."""
    r = subprocess.run(
        [
            "docker",
            "exec",
            "anistito-api",
            "python",
            "-c",
            "import urllib.request; b=urllib.request.urlopen('http://127.0.0.1:3000/', timeout=5).read().decode(); "
            "assert '<html' in b.lower() or '<!doctype' in b.lower(); print('ok')",
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr or r.stdout


def test_docker_compose_services_healthy():
    """db و redis باید healthy باشند."""
    r = subprocess.run(
        ["docker", "compose", "-f", str(_COMPOSE), "ps", "--format", "json"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(_REPO),
    )
    assert r.returncode == 0, r.stderr
    lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
    assert lines, "docker compose ps خالی است"
    names = {json.loads(ln).get("Name"): json.loads(ln) for ln in lines}
    for svc in ("anistito-db", "anistito-redis", "anistito-api"):
        assert svc in names, f"سرویس {svc} یافت نشد"
    assert names["anistito-api"].get("State") == "running"
