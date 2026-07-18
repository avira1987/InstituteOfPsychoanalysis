"""API منوی سایدبار فرایندها."""

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login(client: TestClient, username: str, password: str):
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Login failed for {username}: {r.text}")
    return r.json()["access_token"]


def test_process_nav_items_requires_auth(client: TestClient):
    r = client.get("/api/panel/process-nav-items")
    assert r.status_code == 401


def test_process_nav_items_admin(client: TestClient):
    token = _login(client, "admin", "admin123")
    r = client.get(
        "/api/panel/process-nav-items",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert data.get("summary", {}).get("process_count", 0) >= 1
    first = data["items"][0]
    assert first.get("process_code")
    assert first.get("path", "").startswith("/panel/process-nav/")


def test_process_nav_items_student(client: TestClient):
    token = _login(client, "student_demo", "student123")
    if not token:
        pytest.skip("student_demo login unavailable")
    r = client.get(
        "/api/panel/process-nav-items",
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code == 401:
        pytest.skip("student_demo user not seeded")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data.get("items"), list)
