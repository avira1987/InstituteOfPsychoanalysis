"""فیکسچرهای E2E: سرور uvicorn واقعی + صفحهٔ Playwright."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest
from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ADMIN_DIST = PROJECT_ROOT / "admin-ui" / "dist"


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def _wait_http(url: str, timeout: float = 60.0) -> None:
    deadline = time.time() + timeout
    last_err = None
    while time.time() < deadline:
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                return
        except Exception as e:
            last_err = e
        time.sleep(0.25)
    raise RuntimeError(f"سرور آماده نشد: {url} (آخرین خطا: {last_err})")


@pytest.fixture(scope="session")
def e2e_server_url():
    """uvicorn روی پورت آزاد — همان PostgreSQL (پیش‌فرض: localhost، همان docker-compose)."""
    if not ADMIN_DIST.is_dir():
        pytest.skip("admin-ui/dist لازم است — در پوشه admin-ui: npm run build")

    pytest.importorskip("playwright")

    port = _free_port()
    db_url = os.environ.get(
        "E2E_DATABASE_URL",
        "postgresql+asyncpg://anistito:anistito@127.0.0.1:5432/anistito",
    )

    env = os.environ.copy()
    env["DATABASE_URL"] = db_url
    env["DATABASE_URL_SYNC"] = db_url.replace("postgresql+asyncpg://", "postgresql://")
    env["SLA_CHECK_INTERVAL_SECONDS"] = "86400"
    env["CALENDAR_TRIGGER_INTERVAL_SECONDS"] = "86400"
    env["CALENDAR_TRIGGERS_ENABLED"] = "false"

    mig = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
    )
    if mig.returncode != 0:
        pytest.skip(
            "alembic upgrade failed — run Postgres and create DB/migrations. stderr: "
            + (mig.stderr or "")[:500]
        )

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
    ]
    proc = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_http(f"{base}/health")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()


def _launch_browser(p):
    """اول Playwright Chromium؛ در صورت نصب‌نشدن باینری، Chrome یا Edge سیستم."""
    attempts = (
        {"headless": True},
        {"headless": True, "channel": "chrome"},
        {"headless": True, "channel": "msedge"},
    )
    last = None
    for kwargs in attempts:
        try:
            return p.chromium.launch(**kwargs)
        except Exception as e:
            last = e
            continue
    raise RuntimeError(
        "مرورگر برای Playwright باز نشد. اجرا کنید: python -m playwright install chromium "
        "یا Google Chrome / Microsoft Edge را نصب کنید."
    ) from last


@pytest.fixture
def playwright_page(e2e_server_url: str):
    """یک صفحهٔ Chromium بدون سر (مناسب CI)."""
    with sync_playwright() as p:
        browser = _launch_browser(p)
        page = browser.new_page()
        page.set_default_timeout(60_000)
        yield page
        browser.close()
