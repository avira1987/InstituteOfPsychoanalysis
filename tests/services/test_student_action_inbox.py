"""تست صندوق اقدام دانشجو — build_student_action_inbox."""

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.meta.seed import load_process
from app.models.operational_models import ProcessInstance, Student, User
from app.services.student_tracker_summary import build_student_action_inbox

PROCESSES_DIR = Path(__file__).resolve().parents[2] / "metadata" / "processes"


async def _make_student(db_session: AsyncSession, username: str = "stu_inbox") -> Student:
    user = User(
        id=uuid.uuid4(),
        username=username,
        hashed_password="x",
        role="student",
    )
    student = Student(
        id=uuid.uuid4(),
        user_id=user.id,
        student_code=f"STU-{username}",
        course_type="comprehensive",
        is_intern=False,
        term_count=1,
        current_term=1,
        weekly_sessions=2,
        extra_data={},
    )
    db_session.add_all([user, student])
    await db_session.commit()
    return student


@pytest.mark.asyncio
async def test_action_inbox_filters_staff_role_states(db_session: AsyncSession):
    await load_process(db_session, PROCESSES_DIR / "session_payment.json")
    await load_process(db_session, PROCESSES_DIR / "start_therapy.json")
    await db_session.commit()

    student = await _make_student(db_session, "stu_inbox_role")

    pay_id = uuid.uuid4()
    therapy_id = uuid.uuid4()
    db_session.add_all(
        [
            ProcessInstance(
                id=pay_id,
                process_code="session_payment",
                student_id=student.id,
                current_state_code="payment_due",
                is_completed=False,
                is_cancelled=False,
            ),
            ProcessInstance(
                id=therapy_id,
                process_code="start_therapy",
                student_id=student.id,
                current_state_code="first_session_24h_check",
                is_completed=False,
                is_cancelled=False,
            ),
        ]
    )
    await db_session.commit()

    out = await build_student_action_inbox(db_session, student)
    codes = {it["process_code"] for it in out["items"]}
    assert "session_payment" in codes
    assert "start_therapy" not in codes
    assert out["total"] == 1


@pytest.mark.asyncio
async def test_action_inbox_primary_first(db_session: AsyncSession):
    await load_process(db_session, PROCESSES_DIR / "session_payment.json")
    await load_process(db_session, PROCESSES_DIR / "extra_session.json")
    await db_session.commit()

    student = await _make_student(db_session, "stu_inbox_pri")
    pay_id = uuid.uuid4()
    extra_id = uuid.uuid4()
    student.extra_data = {"primary_instance_id": str(pay_id)}
    db_session.add_all(
        [
            ProcessInstance(
                id=extra_id,
                process_code="extra_session",
                student_id=student.id,
                current_state_code="extra_request",
                is_completed=False,
                is_cancelled=False,
            ),
            ProcessInstance(
                id=pay_id,
                process_code="session_payment",
                student_id=student.id,
                current_state_code="payment_due",
                is_completed=False,
                is_cancelled=False,
            ),
        ]
    )
    await db_session.commit()
    await db_session.refresh(student)

    out = await build_student_action_inbox(db_session, student)
    assert len(out["items"]) >= 2
    assert out["items"][0]["instance_id"] == str(pay_id)
    assert out["items"][0]["is_primary"] is True


@pytest.mark.asyncio
async def test_action_inbox_hint_when_no_actable(db_session: AsyncSession):
    student = await _make_student(db_session, "stu_inbox_hint")
    student.extra_data = {
        "dashboard_therapy_hint_fa": "برای شرکت در جلسات به تب جلسات آنلاین بروید.",
    }
    db_session.add(student)
    await db_session.commit()

    out = await build_student_action_inbox(db_session, student)
    assert out["total"] == 1
    assert out["items"][0]["kind"] == "hint"
    assert "جلسات آنلاین" in out["items"][0]["task_fa"]
    assert "tab=sessions" in out["items"][0]["action_path"]


@pytest.mark.asyncio
async def test_action_inbox_excludes_prep_process(db_session: AsyncSession):
    await load_process(db_session, PROCESSES_DIR / "fall_semester_preparation.json")
    await db_session.commit()

    student = await _make_student(db_session, "stu_inbox_prep")
    prep_id = uuid.uuid4()
    db_session.add(
        ProcessInstance(
            id=prep_id,
            process_code="fall_semester_preparation",
            student_id=student.id,
            current_state_code="calendar_entry",
            is_completed=False,
            is_cancelled=False,
        )
    )
    await db_session.commit()

    out = await build_student_action_inbox(db_session, student)
    assert out["total"] == 0
