"""صف نمونهٔ فرایند برای نقش پنل — API و سرویس."""

from datetime import datetime, timezone
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from app.core.engine import StateMachineEngine
from app.main import app
from app.meta.seed import load_process
from app.services.portal_role_inbox import build_portal_role_process_inbox
from app.services.semester_prep_service import get_or_start_prep_instance


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


@pytest.mark.asyncio
async def test_staff_inbox_shows_interviewer_assignment_after_marketing(
    db_session, sample_user
):
    """پس از مرحلهٔ بازاریابی، مدیر داخلی باید مرحلهٔ مصاحبه‌ها را در کارتابل ببیند."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session,
        "fall_semester_preparation",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    for trigger in (
        "calendar_submitted",
        "tuition_submitted",
        "license_reviewed",
        "course_list_submitted",
        "courses_finalized",
        "marketing_started",
    ):
        result = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event=trigger,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True, result.error

    out = await build_portal_role_process_inbox(db_session, portal_role="staff")
    process_items = [i for i in out["items"] if i.get("kind") == "process"]
    matching = [
        i
        for i in process_items
        if i.get("process_code") == "fall_semester_preparation"
        and i.get("state_code") == "interviewer_assignment"
    ]
    assert matching, "staff inbox should list interviewer_assignment after marketing_started"
    assert matching[0].get("responsible_role_code") == "staff"

    deputy_out = await build_portal_role_process_inbox(db_session, portal_role="deputy_education")
    deputy_matching = [
        i
        for i in deputy_out["items"]
        if i.get("kind") == "process"
        and i.get("process_code") == "fall_semester_preparation"
        and i.get("state_code") == "interviewer_assignment"
    ]
    assert not deputy_matching, "deputy must not see interviewer_assignment after policy change"


@pytest.mark.asyncio
async def test_staff_inbox_shows_winter_interviewer_assignment_after_marketing(
    db_session, sample_user
):
    """پس از بازاریابی زمستان، مدیر داخلی باید مرحلهٔ مصاحبه‌ها را در کارتابل ببیند."""
    processes_dir = Path(__file__).resolve().parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    fall, _ = await get_or_start_prep_instance(
        db_session,
        "fall_semester_preparation",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    fall.is_completed = True
    fall.current_state_code = "published"
    fall.completed_at = datetime.now(timezone.utc)
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session,
        "winter_semester_preparation",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()

    for trigger in (
        "license_reviewed",
        "course_list_reviewed",
        "courses_finalized",
        "marketing_started",
    ):
        result = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event=trigger,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True, result.error

    out = await build_portal_role_process_inbox(db_session, portal_role="staff")
    process_items = [i for i in out["items"] if i.get("kind") == "process"]
    matching = [
        i
        for i in process_items
        if i.get("process_code") == "winter_semester_preparation"
        and i.get("state_code") == "interviewer_assignment"
    ]
    assert matching, "staff inbox should list winter interviewer_assignment after marketing_started"
    assert matching[0].get("responsible_role_code") == "staff"
