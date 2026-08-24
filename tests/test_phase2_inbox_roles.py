"""فاز ۲: کارتابل و آمادگی با اجتماع نقش‌های عملیاتی."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_password_hash
from app.meta.seed import load_process
from app.models.operational_models import InterviewSlot, ProcessInstance, User
from app.services.operator_readiness import compute_operator_readiness_alerts
from app.services.portal_role_inbox import build_user_process_inbox


PROCESSES_DIR = Path(__file__).resolve().parent.parent / "metadata" / "processes"


async def _make_user(
    db: AsyncSession,
    *,
    role: str,
    prefix: str,
    roles: list[str] | None = None,
) -> User:
    user = User(
        id=uuid.uuid4(),
        username=f"{prefix}_{uuid.uuid4().hex[:10]}",
        email=f"{prefix}_{uuid.uuid4().hex[:10]}@t.test",
        hashed_password=get_password_hash("x"),
        full_name_fa=prefix,
        role=role,
        roles=list(roles) if roles is not None else [role],
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


@pytest.mark.asyncio
async def test_user_inbox_student_primary_empty(db_session: AsyncSession, sample_student):
    student_user = await db_session.get(User, sample_student.user_id)
    assert student_user is not None
    out = await build_user_process_inbox(db_session, student_user)
    assert out["items"] == []
    assert out["summary"]["portal_role"] == "student"


@pytest.mark.asyncio
async def test_dual_role_inbox_includes_interviewer_state(
    db_session: AsyncSession, sample_student
) -> None:
    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await db_session.commit()

    dual = await _make_user(
        db_session,
        role="therapist",
        prefix="dual_inb",
        roles=["therapist", "interviewer"],
    )
    only_therapist = await _make_user(
        db_session, role="therapist", prefix="ther_inb", roles=["therapist"]
    )
    staff = await _make_user(db_session, role="staff", prefix="staff_inb")
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="interview_completed",
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.flush()
    t0 = datetime.now(timezone.utc) + timedelta(hours=1)
    db_session.add(
        InterviewSlot(
            id=uuid.uuid4(),
            starts_at=t0,
            ends_at=t0 + timedelta(hours=1),
            course_type="introductory",
            mode="in_person",
            created_by=staff.id,
            interviewer_user_id=dual.id,
            assigned_student_id=sample_student.id,
            assigned_instance_id=inst.id,
        )
    )
    await db_session.commit()

    dual_out = await build_user_process_inbox(db_session, dual)
    dual_ids = {
        i.get("instance_id")
        for i in dual_out["items"]
        if i.get("kind") == "process"
    }
    assert str(inst.id) in dual_ids

    ther_out = await build_user_process_inbox(db_session, only_therapist)
    ther_ids = {
        i.get("instance_id")
        for i in ther_out["items"]
        if i.get("kind") == "process"
    }
    assert str(inst.id) not in ther_ids


@pytest.mark.asyncio
async def test_faculty_1_inbox_includes_supervisor_review(
    db_session: AsyncSession, sample_student
) -> None:
    await load_process(db_session, PROCESSES_DIR / "supervision_session_increase.json")
    await db_session.commit()

    faculty = await _make_user(
        db_session, role="faculty_1", prefix="fac_inb", roles=["faculty_1"]
    )
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="supervision_session_increase",
        student_id=sample_student.id,
        current_state_code="supervisor_review",
        context_data={},
        is_completed=False,
        is_cancelled=False,
    )
    db_session.add(inst)
    await db_session.commit()

    out = await build_user_process_inbox(db_session, faculty)
    ids = {i.get("instance_id") for i in out["items"] if i.get("kind") == "process"}
    assert str(inst.id) in ids
    assert out["summary"]["portal_role"] == "faculty_1"


@pytest.mark.asyncio
async def test_readiness_student_empty():
    u = SimpleNamespace(role="student", roles=["student"], id=uuid.uuid4())
    db = AsyncMock()
    out = await compute_operator_readiness_alerts(db, u)
    assert out == []


@pytest.mark.asyncio
async def test_readiness_loops_therapist_and_staff_roles():
    u = SimpleNamespace(
        role="therapist",
        roles=["therapist", "staff"],
        id=uuid.uuid4(),
    )

    async def _fake_single(_db, _user, role, _rules, _defaults):
        return [{"id": f"alert-{role}", "title_fa": role}]

    with patch(
        "app.services.operator_readiness._compute_readiness_for_single_user",
        side_effect=_fake_single,
    ):
        out = await compute_operator_readiness_alerts(AsyncMock(), u)
    ids = {a["id"] for a in out}
    assert "alert-therapist" in ids
    assert "alert-staff" in ids
