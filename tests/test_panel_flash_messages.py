"""پیام‌های پاپ‌آپ UI — API، سرویس، و ادغام در فید اعلان‌ها."""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.panel_action_notifications import build_action_notifications
from app.services.panel_flash_messages import create_panel_flash_message


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login_token(client: TestClient) -> str | None:
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        return None
    return r.json()["access_token"]


def test_flash_messages_requires_auth(client: TestClient):
    r = client.post(
        "/api/panel/flash-messages",
        json={"message": "تست", "level": "success"},
    )
    assert r.status_code == 401


def test_create_flash_message_http(client: TestClient):
    token = _login_token(client)
    if not token:
        pytest.skip("Login failed")
    r = client.post(
        "/api/panel/flash-messages",
        json={"message": "پیام تست پاپ‌آپ", "level": "success", "source_path": "/panel/test"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    assert data.get("id")


def test_action_notifications_includes_flash_message(client: TestClient):
    token = _login_token(client)
    if not token:
        pytest.skip("Login failed")
    headers = {"Authorization": f"Bearer {token}"}
    msg = "پیام یکتا برای فید اعلان"
    cr = client.post(
        "/api/panel/flash-messages",
        json={"message": msg, "level": "error"},
        headers=headers,
    )
    assert cr.status_code == 200
    r = client.get("/api/panel/action-notifications?limit=50&offset=0", headers=headers)
    assert r.status_code == 200
    items = r.json().get("items") or []
    flash = [i for i in items if i.get("kind") == "flash_message" and msg in (i.get("summary_fa") or "")]
    assert len(flash) >= 1
    assert flash[0].get("level") == "error"
    assert flash[0].get("title_fa") == "خطا"


@pytest.mark.asyncio
async def test_build_action_notifications_includes_flash(db_session, sample_user):
    await create_panel_flash_message(
        db_session,
        user_id=sample_user.id,
        message="پیام async تست",
        level="success",
        source_path="/panel/foo",
    )
    await db_session.commit()
    out = await build_action_notifications(db_session, sample_user, limit=20, offset=0)
    flash = [i for i in out["items"] if i.get("kind") == "flash_message"]
    assert any("پیام async تست" in (i.get("summary_fa") or "") for i in flash)
