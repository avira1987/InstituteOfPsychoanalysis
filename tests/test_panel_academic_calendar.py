"""Panel API — تقویم آموزشی فعال برای دانشجو."""

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login_headers(client: TestClient, username: str, password: str) -> dict:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_panel_academic_calendar_active_admin_ok(client: TestClient):
    """admin می‌تواند تقویم فعال را بخواند (null اگر منتشر نشده)."""
    headers = _login_headers(client, "admin", "admin123")
    r = client.get("/api/panel/academic-calendar/active", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data is None or isinstance(data, dict)


def test_panel_academic_calendar_unauthenticated(client: TestClient):
    r = client.get("/api/panel/academic-calendar/active")
    assert r.status_code == 401
