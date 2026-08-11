"""Panel API — لیست یکپارچهٔ جلسات آنلاین دانشجو."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.main import app
from app.models.operational_models import InterviewSlot, Student, TherapySession, User
from app.services.action_handler import ActionHandler
from app.services.student_online_sessions_service import list_student_online_sessions
from sqlalchemy.orm.attributes import flag_modified


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _login_headers(client: TestClient, username: str, password: str = "testpass") -> dict:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.mark.asyncio
async def test_list_student_online_sessions_aggregates_sources(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
):
    therapist = User(
        id=uuid.uuid4(),
        username=f"th_{uuid.uuid4().hex[:8]}",
        email=f"th_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password="x",
        role="therapist",
        is_active=True,
        full_name_fa="دکتر درمانگر نمونه",
    )
    db_session.add(therapist)
    await db_session.flush()
    sample_student.therapist_id = therapist.id

    future = datetime.now(timezone.utc) + timedelta(days=3)
    session_end = future + timedelta(hours=1)
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=therapist.id,
        session_date=future.date(),
        session_starts_at=future,
        status="scheduled",
        payment_status="pending",
        links_unlocked=False,
    )
    db_session.add(ts)

    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=future,
        ends_at=session_end,
        mode="online",
        assigned_student_id=sample_student.id,
        booking_payment_deadline_at=None,
        meeting_link="https://alocom.example/join",
        label_fa="مصاحبه تست",
    )
    db_session.add(slot)

    extra = dict(sample_student.extra_data or {})
    extra["lms"] = {
        "online_links": [
            {
                "id": "sup-1",
                "kind": "supervision_50th",
                "url": "https://example.com/supervision",
                "created_at": future.isoformat(),
            }
        ],
        "portal_course_links": {"THEORY101": "https://example.com/class"},
    }
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    out = await list_student_online_sessions(
        db_session, sample_student, sample_student_user, include_past=False
    )
    kinds = {item["kind"] for item in out["items"]}
    assert "therapy" in kinds
    assert "interview" in kinds
    assert "supervision" in kinds
    assert "course" in kinds
    assert out["summary"]["total"] >= 4

    therapy_items = [x for x in out["items"] if x["kind"] == "therapy"]
    assert therapy_items[0]["meeting_link"] is None
    assert therapy_items[0]["meeting_link_is_visible"] is False
    assert therapy_items[0]["therapist_name_fa"] == "دکتر درمانگر نمونه"


@pytest.mark.asyncio
async def test_therapy_link_visible_when_unlocked(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
):
    future = date.today() + timedelta(days=5)
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=None,
        session_date=future,
        status="scheduled",
        payment_status="paid",
        meeting_url="https://skyroom.example/room",
        links_unlocked=True,
        meeting_provider="skyroom",
    )
    db_session.add(ts)
    await db_session.commit()

    out = await list_student_online_sessions(
        db_session, sample_student, sample_student_user, include_past=False
    )
    therapy_items = [x for x in out["items"] if x["kind"] == "therapy"]
    assert len(therapy_items) == 1
    assert therapy_items[0]["meeting_link"] == "https://skyroom.example/room"
    assert therapy_items[0]["meeting_link_is_visible"] is True


@pytest.mark.asyncio
async def test_enable_online_session_link_unlocks_paid_sessions(
    db_session: AsyncSession,
    sample_student: Student,
):
    from app.models.operational_models import ProcessInstance

    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=None,
        session_date=date.today() + timedelta(days=2),
        status="scheduled",
        payment_status="paid",
        links_unlocked=False,
    )
    db_session.add(ts)
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="therapist_session_cancellation",
        student_id=sample_student.id,
        current_state_code="x",
    )
    db_session.add(inst)
    await db_session.flush()

    handler = ActionHandler(db_session)
    detail = await handler._handle_enable_online_link({}, inst, {})
    await db_session.commit()
    await db_session.refresh(ts)

    assert "online_session_link_enabled" in detail
    assert ts.links_unlocked is True


@pytest.mark.asyncio
async def test_panel_my_online_sessions_api_for_student(
    db_session: AsyncSession,
    sample_student: Student,
    sample_student_user: User,
    client: TestClient,
):
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=None,
        session_date=date.today() + timedelta(days=4),
        status="scheduled",
        payment_status="pending",
    )
    db_session.add(ts)
    await db_session.commit()

    headers = _login_headers(client, sample_student_user.username)
    r = client.get("/api/panel/my-online-sessions", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["summary"]["total"] >= 1
    assert any(x["kind"] == "therapy" for x in data["items"])


@pytest.mark.asyncio
async def test_therapy_patch_auto_unlocks_link_for_paid_session(
    db_session: AsyncSession,
    sample_student: Student,
    sample_user: User,
    client: TestClient,
):
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=sample_user.id,
        session_date=date.today() + timedelta(days=6),
        status="scheduled",
        payment_status="paid",
        links_unlocked=False,
    )
    db_session.add(ts)
    await db_session.commit()

    headers = _login_headers(client, sample_user.username)
    r = client.patch(
        f"/api/therapy-sessions/{ts.id}",
        headers=headers,
        json={"meeting_url": "https://skyroom.example/student", "meeting_provider": "skyroom"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["links_unlocked"] is True
    assert body["meeting_url"] == "https://skyroom.example/student"

    student_headers = _login_headers(client, (await _student_username(db_session, sample_student)))
    agg = client.get("/api/panel/my-online-sessions", headers=student_headers)
    assert agg.status_code == 200
    therapy = [x for x in agg.json()["items"] if x["kind"] == "therapy"]
    assert therapy[0]["meeting_link_is_visible"] is True


async def _student_username(db_session: AsyncSession, student: Student) -> str:
    from sqlalchemy import select

    u = (
        await db_session.execute(select(User).where(User.id == student.user_id))
    ).scalars().first()
    assert u is not None
    return u.username


@pytest.mark.asyncio
async def test_panel_my_online_sessions_forbidden_for_admin(
    sample_user: User,
    client: TestClient,
):
    headers = _login_headers(client, sample_user.username)
    r = client.get("/api/panel/my-online-sessions", headers=headers)
    assert r.status_code == 403
