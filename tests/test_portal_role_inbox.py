"""صف نمونهٔ فرایند برای نقش پنل — API و سرویس."""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.portal_role_inbox import build_portal_role_process_inbox


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.mark.asyncio
async def test_build_portal_inbox_student_empty(db_session):
    out = await build_portal_role_process_inbox(db_session, portal_role="student")
    assert out["items"] == []
    assert out["summary"]["portal_role"] == "student"


def test_my_process_inbox_requires_auth(client: TestClient):
    r = client.get("/api/panel/my-process-inbox")
    assert r.status_code == 401


def test_my_process_inbox_admin_returns_items_key(client: TestClient):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.text}")
    token = r.json()["access_token"]
    r2 = client.get(
        "/api/panel/my-process-inbox",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert "items" in data
    assert "summary" in data
