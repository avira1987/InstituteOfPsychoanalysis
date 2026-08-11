"""Therapist therapy-session APIs — for-therapist + attendance-workbench."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.api.auth import get_password_hash
from app.main import app
from app.models.operational_models import ProcessInstance, Student, TherapySession, User


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _login_headers(client: TestClient, username: str, password: str = "testpass") -> dict:
    r = client.post("/api/auth/login", data={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _make_therapist(db_session: AsyncSession) -> User:
    suid = uuid.uuid4().hex[:12]
    user = User(
        id=uuid.uuid4(),
        username=f"therapist_test_{suid}",
        email=f"therapist_{suid}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="درمانگر تست",
        role="therapist",
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_for_therapist_includes_sessions_via_student_therapist_id(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    """جلسه با therapist_id خالی ولی دانشجو وصل به درمانگر باید در لیست بیاید و پر شود."""
    therapist = await _make_therapist(db_session)
    sample_student.therapist_id = therapist.id
    await db_session.commit()

    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=None,
        session_date=date.today() + timedelta(days=3),
        status="scheduled",
        payment_status="paid",
        meeting_url="https://alocom.example/student?token=orphan",
        links_unlocked=True,
    )
    db_session.add(ts)
    await db_session.commit()

    headers = _login_headers(client, therapist.username)
    r = client.get("/api/therapy-sessions/for-therapist", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert any(x["id"] == str(ts.id) for x in rows)
    row = next(x for x in rows if x["id"] == str(ts.id))
    assert row["therapist_id"] == str(therapist.id)

    await db_session.refresh(ts)
    assert ts.therapist_id == therapist.id


@pytest.mark.asyncio
async def test_for_therapist_returns_host_link_and_student_code(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=therapist.id,
        session_date=date.today() + timedelta(days=2),
        status="scheduled",
        payment_status="paid",
        meeting_url="https://alocom.example/student?token=stu",
        host_meeting_url="https://alocom.example/host?token=host",
        meeting_provider="alocom",
        links_unlocked=True,
        alocom_event_id="evt-1",
    )
    db_session.add(ts)
    await db_session.commit()

    headers = _login_headers(client, therapist.username)
    r = client.get("/api/therapy-sessions/for-therapist", headers=headers)
    assert r.status_code == 200, r.text
    rows = r.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["student_code"] == sample_student.student_code
    assert row["student_meeting_url_ready"] is True
    assert row["meeting_url"] == "https://alocom.example/host?token=host"
    assert row["id"] == str(ts.id)


@pytest.mark.asyncio
async def test_attendance_workbench_unpaid_allows_absent_only(
    db_session: AsyncSession,
    sample_student: Student,
    sample_user: User,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=therapist.id,
        session_date=date.today(),
        status="scheduled",
        payment_status="pending",
        meeting_url="https://alocom.example/student?token=stu",
        host_meeting_url="https://alocom.example/host?token=host",
        meeting_provider="alocom",
        links_unlocked=False,
    )
    db_session.add(ts)

    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="attendance_tracking",
        student_id=sample_student.id,
        started_by=sample_user.id,
        current_state_code="therapist_recording",
        context_data={
            "therapy_session_id": str(ts.id),
            "session_id": str(ts.id),
            "session_date": ts.session_date.isoformat(),
            "session_paid": False,
            "student_on_leave": False,
            "session_cancelled": False,
        },
    )
    db_session.add(inst)
    await db_session.commit()

    headers = _login_headers(client, therapist.username)
    r = client.get("/api/therapy-sessions/attendance-workbench", headers=headers)
    assert r.status_code == 200, r.text
    sessions = r.json()["sessions"]
    row = next(x for x in sessions if x["session_id"] == str(ts.id))
    assert row["can_record_present"] is False
    assert row["can_record_absent"] is True
    assert row["can_record"] is True
    assert row["record_block_reason"] == "unpaid"
    assert row["meeting_url"] == "https://alocom.example/host?token=host"
    assert row["student_meeting_url_ready"] is True
    assert row["links_unlocked"] is False


@pytest.mark.asyncio
async def test_attendance_workbench_paid_allows_present_and_absent(
    db_session: AsyncSession,
    sample_student: Student,
    sample_user: User,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=therapist.id,
        session_date=date.today(),
        status="scheduled",
        payment_status="paid",
        meeting_url="https://skyroom.example/student",
        links_unlocked=True,
    )
    db_session.add(ts)

    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="attendance_tracking",
        student_id=sample_student.id,
        started_by=sample_user.id,
        current_state_code="therapist_recording",
        context_data={
            "therapy_session_id": str(ts.id),
            "session_id": str(ts.id),
            "session_date": ts.session_date.isoformat(),
            "session_paid": True,
            "student_on_leave": False,
            "session_cancelled": False,
        },
    )
    db_session.add(inst)
    await db_session.commit()

    headers = _login_headers(client, therapist.username)
    r = client.get("/api/therapy-sessions/attendance-workbench", headers=headers)
    assert r.status_code == 200, r.text
    row = next(x for x in r.json()["sessions"] if x["session_id"] == str(ts.id))
    assert row["can_record_present"] is True
    assert row["can_record_absent"] is True
    assert row["can_record"] is True
    assert row["record_block_reason"] is None


@pytest.mark.asyncio
async def test_patch_links_unlocked_requires_paid_and_student_link(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=therapist.id,
        session_date=date.today() + timedelta(days=1),
        status="scheduled",
        payment_status="paid",
        meeting_url="https://alocom.example/student?token=stu",
        links_unlocked=False,
    )
    db_session.add(ts)
    await db_session.commit()

    headers = _login_headers(client, therapist.username)
    ok = client.patch(
        f"/api/therapy-sessions/{ts.id}",
        headers=headers,
        json={"links_unlocked": True},
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["links_unlocked"] is True

    unpaid = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=therapist.id,
        session_date=date.today() + timedelta(days=2),
        status="scheduled",
        payment_status="pending",
        meeting_url="https://alocom.example/student?token=stu2",
        links_unlocked=False,
    )
    db_session.add(unpaid)
    await db_session.commit()

    bad = client.patch(
        f"/api/therapy-sessions/{unpaid.id}",
        headers=headers,
        json={"links_unlocked": True},
    )
    assert bad.status_code == 409
