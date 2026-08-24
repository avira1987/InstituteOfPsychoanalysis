"""Therapy workbench API — summary without side-effects, explicit repair."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.testclient import TestClient

from app.api.auth import get_password_hash
from app.main import app
from app.models.operational_models import Student, TherapySession, User


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
        username=f"wb_therapist_{suid}",
        email=f"wb_therapist_{suid}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa="درمانگر میزکار",
        role="therapist",
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _session_count(db_session: AsyncSession, student_id: uuid.UUID) -> int:
    q = select(func.count()).select_from(TherapySession).where(TherapySession.student_id == student_id)
    return int((await db_session.execute(q)).scalar_one())


@pytest.mark.asyncio
async def test_workbench_summary_has_no_seed_side_effect(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    sample_student.therapist_id = therapist.id
    sample_student.therapy_started = True
    await db_session.commit()

    before = await _session_count(db_session, sample_student.id)
    headers = _login_headers(client, therapist.username)

    with patch(
        "app.services.therapy_session_schedule.repair_student_therapy_continuity",
    ) as mock_repair:
        r = client.get("/api/therapy-workbench/summary", headers=headers)
        assert r.status_code == 200, r.text
        mock_repair.assert_not_called()

    after = await _session_count(db_session, sample_student.id)
    assert after == before
    body = r.json()
    assert "totals" in body
    assert "students" in body
    row = next((s for s in body["students"] if s["student_id"] == str(sample_student.id)), None)
    assert row is not None
    assert row["missing_future_schedule"] is True


@pytest.mark.asyncio
async def test_for_therapist_does_not_call_repair(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    sample_student.therapist_id = therapist.id
    sample_student.therapy_started = True
    ts = TherapySession(
        id=uuid.uuid4(),
        student_id=sample_student.id,
        therapist_id=therapist.id,
        session_date=date.today() + timedelta(days=2),
        status="scheduled",
        payment_status="paid",
    )
    db_session.add(ts)
    await db_session.commit()

    headers = _login_headers(client, therapist.username)
    with patch(
        "app.services.therapy_session_schedule.repair_student_therapy_continuity",
    ) as mock_repair:
        r = client.get("/api/therapy-sessions/for-therapist", headers=headers)
        assert r.status_code == 200, r.text
        mock_repair.assert_not_called()


@pytest.mark.asyncio
async def test_workbench_repair_creates_future_sessions(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    sample_student.therapist_id = therapist.id
    sample_student.therapy_started = True
    sample_student.weekly_sessions = 1
    await db_session.commit()

    before = await _session_count(db_session, sample_student.id)
    headers = _login_headers(client, therapist.username)

    r = client.post(f"/api/therapy-workbench/repair/{sample_student.id}", headers=headers)
    assert r.status_code == 200, r.text
    after = await _session_count(db_session, sample_student.id)
    assert after > before
    assert (r.json().get("seed") or {}).get("created", 0) >= 1


@pytest.mark.asyncio
async def test_workbench_sessions_paginated_for_student(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    sample_student.therapist_id = therapist.id
    sample_student.therapy_started = True
    paid_id = uuid.uuid4()
    for i in range(3):
        kwargs = {
            "id": paid_id if i == 0 else uuid.uuid4(),
            "student_id": sample_student.id,
            "therapist_id": therapist.id,
            "session_date": date.today() + timedelta(days=i + 1),
            "status": "scheduled",
            "payment_status": "paid" if i == 0 else "pending",
        }
        if i == 0:
            kwargs.update(
                meeting_url="https://alocom.example/student?token=stu",
                host_meeting_url="https://alocom.example/host?token=host",
                meeting_provider="alocom",
                links_unlocked=False,
            )
        db_session.add(TherapySession(**kwargs))
    await db_session.commit()

    headers = _login_headers(client, therapist.username)
    r = client.get(
        "/api/therapy-workbench/sessions",
        headers=headers,
        params={"student_id": str(sample_student.id), "page_size": 2},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["sessions"]) <= 2
    assert body["pagination"]["total"] >= 3
    paid_row = next(x for x in body["sessions"] if x["session_id"] == str(paid_id))
    assert paid_row["meeting_url"] == "https://alocom.example/host?token=host"
    assert paid_row["student_meeting_url_ready"] is True
    assert paid_row["links_unlocked"] is False
    assert paid_row["payment_status"] == "paid"


@pytest.mark.asyncio
async def test_workbench_repair_denied_for_unassigned_therapist(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    other = await _make_therapist(db_session)
    sample_student.therapist_id = other.id
    sample_student.therapy_started = True
    await db_session.commit()

    headers = _login_headers(client, therapist.username)
    r = client.post(f"/api/therapy-workbench/repair/{sample_student.id}", headers=headers)
    assert r.status_code == 403


async def _make_role_user(db_session: AsyncSession, role: str) -> User:
    suid = uuid.uuid4().hex[:12]
    user = User(
        id=uuid.uuid4(),
        username=f"wb_{role}_{suid}",
        email=f"wb_{role}_{suid}@test.com",
        hashed_password=get_password_hash("testpass"),
        full_name_fa=f"کاربر {role}",
        role=role,
        roles=[role],
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest.mark.asyncio
async def test_admin_workbench_therapist_scope_sees_other_therapist_students(
    db_session: AsyncSession,
    sample_student: Student,
    client: TestClient,
):
    therapist = await _make_therapist(db_session)
    admin = await _make_role_user(db_session, "admin")
    sample_student.therapist_id = therapist.id
    sample_student.therapy_started = True
    await db_session.commit()

    headers = _login_headers(client, admin.username)
    r = client.get(
        "/api/therapy-workbench/summary",
        headers=headers,
        params={"role_scope": "therapist"},
    )
    assert r.status_code == 200, r.text
    row = next(
        (s for s in r.json().get("students") or [] if s["student_id"] == str(sample_student.id)),
        None,
    )
    assert row is not None


@pytest.mark.asyncio
async def test_staff_workbench_therapist_scope_forbidden(
    db_session: AsyncSession,
    client: TestClient,
):
    staff = await _make_role_user(db_session, "staff")
    headers = _login_headers(client, staff.username)
    r = client.get(
        "/api/therapy-workbench/summary",
        headers=headers,
        params={"role_scope": "therapist"},
    )
    assert r.status_code == 403
