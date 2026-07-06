"""بستن اعلان‌های اقدام — API، حذف خودکار پس از انجام کار."""

import uuid
from datetime import date, datetime, timezone

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.models.operational_models import PanelTaskReminder, ProcessInstance
from app.services.panel_action_notifications import build_action_notifications
from app.services.panel_flash_messages import create_panel_flash_message
from app.services.panel_notification_dismiss import (
    dismiss_action_notification,
    dismiss_notifications_for_instance,
    prune_stale_task_reminders,
)


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def _login_token(client: TestClient) -> str | None:
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    if r.status_code != 200:
        return None
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_dismiss_flash_removes_from_feed(db_session, sample_user):
    row = await create_panel_flash_message(
        db_session,
        user_id=sample_user.id,
        message="پیام قابل بستن",
        level="success",
    )
    await db_session.commit()
    nid = f"flash:{row.id}"
    ok = await dismiss_action_notification(db_session, user_id=sample_user.id, notification_id=nid)
    assert ok is True
    await db_session.commit()
    out = await build_action_notifications(db_session, sample_user, limit=50, offset=0)
    assert not any(i.get("notification_id") == nid for i in out["items"])


@pytest.mark.asyncio
async def test_prune_stale_task_reminder_when_instance_not_active(
    db_session, sample_user, sample_student, sample_process
):
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="test_process",
        student_id=sample_student.id,
        current_state_code="initial",
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.flush()
    rem = PanelTaskReminder(
        user_id=sample_user.id,
        kind="daily_overdue",
        title_fa="کار عقب‌افتاده",
        summary_fa="تست",
        action_path="/panel/students",
        instance_id=inst.id,
        student_id=sample_student.id,
        process_code="test_process",
        state_code="initial",
        run_date_tehran=date.today(),
        fingerprint=f"test-{uuid.uuid4()}",
    )
    db_session.add(rem)
    await db_session.commit()

    await prune_stale_task_reminders(
        db_session,
        user_id=sample_user.id,
        active_instance_ids=set(),
    )
    await db_session.commit()
    await db_session.refresh(rem)
    assert rem.dismissed_at is not None


@pytest.mark.asyncio
async def test_dismiss_for_instance_closes_process_and_reminder(
    db_session, sample_user, sample_student, sample_process
):
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="test_process",
        student_id=sample_student.id,
        current_state_code="initial",
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.flush()
    rem = PanelTaskReminder(
        user_id=sample_user.id,
        kind="daily_overdue",
        title_fa="کار عقب‌افتاده",
        summary_fa="تست",
        action_path="/panel/students",
        instance_id=inst.id,
        student_id=sample_student.id,
        process_code="test_process",
        state_code="initial",
        run_date_tehran=date.today(),
        fingerprint=f"test-{uuid.uuid4()}",
    )
    db_session.add(rem)
    await db_session.commit()

    await dismiss_notifications_for_instance(
        db_session,
        user_id=sample_user.id,
        instance_id=inst.id,
    )
    await db_session.commit()
    await db_session.refresh(rem)
    assert rem.dismissed_at is not None

    out = await build_action_notifications(db_session, sample_user, limit=50, offset=0)
    assert not any(i.get("notification_id") == f"process:{inst.id}" for i in out["items"])


def test_dismiss_action_notification_http(client: TestClient):
    token = _login_token(client)
    if not token:
        pytest.skip("Login failed")
    headers = {"Authorization": f"Bearer {token}"}
    cr = client.post(
        "/api/panel/flash-messages",
        json={"message": "پیام برای dismiss http", "level": "success"},
        headers=headers,
    )
    assert cr.status_code == 200
    flash_id = cr.json().get("id")
    assert flash_id
    nid = f"flash:{flash_id}"
    dr = client.post(
        "/api/panel/action-notifications/dismiss",
        json={"notification_id": nid},
        headers=headers,
    )
    assert dr.status_code == 200
    assert dr.json().get("ok") is True
    r = client.get("/api/panel/action-notifications?limit=50&offset=0", headers=headers)
    assert r.status_code == 200
    items = r.json().get("items") or []
    assert not any(i.get("notification_id") == nid for i in items)
