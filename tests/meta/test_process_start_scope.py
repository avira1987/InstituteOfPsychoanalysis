"""Tests for manual process start scope registry and API validation."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.main import app
from app.meta.process_start_scope import (
    INSTITUTE_START_CODES,
    STAFF_START_CODES,
    get_manual_start_scope,
)
from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance, User
from app.services.institute_operational_anchor import (
    ensure_institute_operational_student,
    is_institute_operational_student,
)


def test_get_manual_start_scope_mapping():
    assert get_manual_start_scope("fall_semester_preparation") == "institute"
    assert get_manual_start_scope("winter_semester_preparation") == "institute"
    assert get_manual_start_scope("class_session_cancellation") == "staff"
    assert get_manual_start_scope("live_supervision_session_prep") == "staff"
    assert get_manual_start_scope("live_therapy_observation_session_prep") == "staff"
    assert get_manual_start_scope("class_attendance") == "staff"
    assert get_manual_start_scope("start_therapy") == "student"
    assert get_manual_start_scope("introductory_course_registration") == "student"
    assert INSTITUTE_START_CODES.isdisjoint(STAFF_START_CODES)


def _client_for_user(db_session: AsyncSession, user: User):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_start_institute_via_process_start_rejected(
    db_session: AsyncSession,
    sample_user,
    sample_student,
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    async with _client_for_user(db_session, sample_user) as client:
        res = await client.post(
            "/api/process/start",
            json={
                "process_code": "fall_semester_preparation",
                "student_id": str(sample_student.id),
            },
        )
    app.dependency_overrides.clear()
    assert res.status_code == 400
    assert "آماده‌سازی ترم" in (res.json().get("detail") or "")


@pytest.mark.asyncio
async def test_start_staff_requires_user_id(
    db_session: AsyncSession,
    sample_user,
    sample_student,
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "class_attendance.json")
    await db_session.commit()

    async with _client_for_user(db_session, sample_user) as client:
        res = await client.post(
            "/api/process/start",
            json={
                "process_code": "class_attendance",
                "student_id": str(sample_student.id),
            },
        )
    app.dependency_overrides.clear()
    assert res.status_code == 400
    assert "user_id" in (res.json().get("detail") or "")


@pytest.mark.asyncio
async def test_start_student_on_inst_ops_rejected(
    db_session: AsyncSession,
    sample_user,
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "extra_session.json")
    await db_session.commit()
    anchor = await ensure_institute_operational_student(db_session)
    await db_session.commit()

    async with _client_for_user(db_session, sample_user) as client:
        res = await client.post(
            "/api/process/start",
            json={
                "process_code": "extra_session",
                "student_id": str(anchor.id),
            },
        )
    app.dependency_overrides.clear()
    assert res.status_code == 400
    assert "عملیاتی" in (res.json().get("detail") or "")


@pytest.mark.asyncio
async def test_start_staff_binds_inst_ops_and_subject_user(
    db_session: AsyncSession,
    sample_user,
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "class_attendance.json")
    await db_session.commit()

    subject = User(
        id=uuid.uuid4(),
        username=f"instructor_{uuid.uuid4().hex[:8]}",
        email=f"inst_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=sample_user.hashed_password,
        full_name_fa="مدرس تست",
        role="instructor",
        is_active=True,
    )
    db_session.add(subject)
    await db_session.commit()

    async with _client_for_user(db_session, sample_user) as client:
        res = await client.post(
            "/api/process/start",
            json={
                "process_code": "class_attendance",
                "user_id": str(subject.id),
            },
        )
    app.dependency_overrides.clear()
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["process_code"] == "class_attendance"
    ctx = body.get("context_data") or {}
    assert ctx.get("subject_user_id") == str(subject.id)
    assert ctx.get("subject_username") == subject.username
    assert ctx.get("subject_user_role") == "instructor"

    inst = await db_session.get(ProcessInstance, uuid.UUID(body["instance_id"]))
    assert inst is not None
    from app.models.operational_models import Student

    student = await db_session.get(Student, inst.student_id)
    assert is_institute_operational_student(student) is True
