"""فید اعلان‌های اقدام — API و سرویس."""

import uuid

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models.operational_models import ProcessInstance
from app.services.panel_action_notifications import (
    build_action_notifications,
    notification_action_path,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_action_notifications_requires_auth(client: TestClient):
    r = client.get("/api/panel/action-notifications")
    assert r.status_code == 401


def test_notification_action_path_process_therapist():
    p = notification_action_path(
        {
            "kind": "process",
            "instance_id": "i1",
            "student_id": "s1",
            "responsible_role_code": "therapist",
        }
    )
    assert "/panel/portal/therapist" in p
    assert "instance_id=i1" in p.replace("%3A", ":")  # urlencode may vary
    assert "tab=pending" in p


@pytest.mark.asyncio
async def test_build_action_notifications_student_turn(db_session, sample_student_user, sample_student, sample_process):
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="test_process",
        student_id=sample_student.id,
        current_state_code="initial",
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.commit()

    out = await build_action_notifications(db_session, sample_student_user, limit=10, offset=0)
    assert out["total"] >= 1
    ids = {i.get("instance_id") for i in out["items"]}
    assert str(inst.id) in ids
    one = next(i for i in out["items"] if i.get("instance_id") == str(inst.id))
    assert one.get("summary_fa")
    assert "/panel/portal/student" in (one.get("action_path") or "")
    assert "processes" in (one.get("action_path") or "")


@pytest.mark.asyncio
async def test_build_action_notifications_admin_shape(db_session, sample_user):
    out = await build_action_notifications(db_session, sample_user, limit=5, offset=0)
    assert "items" in out
    assert "total" in out
    assert isinstance(out["items"], list)
    for it in out["items"]:
        assert it.get("notification_id")
        assert it.get("title_fa")
        assert it.get("summary_fa")
        assert it.get("action_path", "").startswith("/panel")


def test_action_notifications_admin_http(client: TestClient):
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        pytest.skip(f"Login failed: {r.text}")
    token = r.json()["access_token"]
    r2 = client.get(
        "/api/panel/action-notifications?limit=5&offset=0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    data = r2.json()
    assert "items" in data
    assert "total" in data
