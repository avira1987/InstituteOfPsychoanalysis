"""Tests for introductory registration readiness gate."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import InvalidTransitionError, StateMachineEngine
from app.meta.course_selection_validation import validate_intro_term1_selected_courses
from app.meta.seed import load_process
from app.services.registration_readiness_service import (
    check_intro_registration_gate,
    map_prep_course_name_to_code,
    prep_courses_rows_to_codes,
)
from app.services.student_service import StudentService
from tests.helpers.registration_gate_fixture import open_intro_registration_gate


def test_map_prep_course_names():
    assert map_prep_course_name_to_code("تئوری روانکاوی ۱") == "theory_1"
    assert map_prep_course_name_to_code("theory_3") == "theory_3"
    rows = [{"course_name": "تئوری روانکاوی ۲"}]
    assert prep_courses_rows_to_codes(rows) == ["theory_2"]


@pytest.mark.asyncio
async def test_gate_closed_without_prep(db_session: AsyncSession):
    gate = await check_intro_registration_gate(db_session)
    assert gate.allowed is False
    assert gate.prep_published is False
    assert gate.reason_fa


@pytest.mark.asyncio
async def test_gate_open_with_fixture(db_session: AsyncSession):
    await open_intro_registration_gate(db_session)
    await db_session.commit()
    gate = await check_intro_registration_gate(db_session)
    assert gate.allowed is True
    assert gate.prep_published is True
    assert gate.calendar_active is True
    assert gate.in_registration_window is True


@pytest.mark.asyncio
async def test_intro_transition_blocked_when_gate_closed(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "introductory_course_registration.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="applicant",
    )
    await db_session.commit()

    transitions = await engine.get_available_transitions(instance.id, "applicant")
    assert transitions == []

    with pytest.raises(InvalidTransitionError):
        await engine.execute_transition(
            instance.id,
            "timeslot_selected",
            sample_user.id,
            "applicant",
            {"selected_timeslot": "2026-05-01T10:00:00"},
        )


@pytest.mark.asyncio
async def test_intro_transition_allowed_when_gate_open(
    db_session: AsyncSession, sample_student, sample_user
):
    await open_intro_registration_gate(db_session)
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "introductory_course_registration.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="applicant",
    )
    await db_session.commit()

    result = await engine.execute_transition(
        instance.id,
        "timeslot_selected",
        sample_user.id,
        "applicant",
        {"selected_timeslot": "2026-05-01T10:00:00"},
    )
    assert result.success is True
    assert result.to_state == "interview_payment"


@pytest.mark.asyncio
async def test_start_initial_process_deferred_when_gate_closed(
    db_session: AsyncSession, sample_student, sample_student_user
):
    sample_student.course_type = "introductory"
    await db_session.commit()
    svc = StudentService(db_session)
    inst = await svc.start_initial_process_for_student(sample_student, sample_student_user)
    assert inst is None
    extra = sample_student.extra_data or {}
    assert not extra.get("primary_instance_id")


@pytest.mark.asyncio
async def test_validate_intro_courses_rejects_missing_admission():
    ok, err = validate_intro_term1_selected_courses({}, ["theory_1"])
    assert ok is False
    assert "مصاحبه" in (err or "")


def test_validate_intro_courses_intersects_offered():
    ctx = {
        "interview_result": "full_admission",
        "admission_type": "full",
        "available_courses": ["theory_1", "theory_2"],
    }
    ok, err = validate_intro_term1_selected_courses(ctx, ["theory_1"])
    assert ok is True
    ok2, err2 = validate_intro_term1_selected_courses(ctx, ["theory_5"])
    assert ok2 is False
