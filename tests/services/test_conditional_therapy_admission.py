"""Tests for conditional therapy admission flags, ensure API, term-end chain, term2 gate."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance, Student
from app.services.action_handler import ActionHandler
from app.services.admission_type_service import (
    ADMISSION_CONDITIONAL_THERAPY,
    derive_has_active_therapist,
    normalize_admission_type,
    persist_admission_type_on_student,
)
from app.services.introductory_registration_chaining import (
    _persist_admission_from_instance,
)
from app.services.student_service import StudentService

PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


@pytest.mark.asyncio
async def test_activate_therapy_sets_has_active_therapist(
    db_session: AsyncSession, sample_student: Student
):
    instance = ProcessInstance(
        id=uuid.uuid4(),
        process_code="start_therapy",
        student_id=sample_student.id,
        current_state_code="payment_pending",
    )
    db_session.add(instance)
    await db_session.flush()

    handler = ActionHandler(db_session)
    await handler.handle_actions([{"type": "activate_therapy"}], instance, {})
    await db_session.commit()
    await db_session.refresh(sample_student)

    assert sample_student.therapy_started is True
    extra = sample_student.extra_data or {}
    assert extra.get("has_active_therapist") is True
    assert derive_has_active_therapist(sample_student, extra) is True


@pytest.mark.asyncio
async def test_persist_admission_type_on_conditional_result(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    instance = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="result_conditional_therapy",
        context_data={
            "interview_result": "conditional_therapy",
            "admission_type": "conditional_therapy",
        },
        started_by=sample_user.id,
    )
    db_session.add(instance)
    await db_session.flush()

    await _persist_admission_from_instance(
        db_session, instance, "result_conditional_therapy"
    )
    await db_session.commit()
    await db_session.refresh(sample_student)

    assert normalize_admission_type(
        (sample_student.extra_data or {}).get("admission_type")
    ) == ADMISSION_CONDITIONAL_THERAPY


@pytest.mark.asyncio
async def test_ensure_conditional_start_therapy_creates_instance(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "start_therapy.json")
    await db_session.commit()

    persist_admission_type_on_student(
        sample_student, admission_type=ADMISSION_CONDITIONAL_THERAPY
    )
    sample_student.therapy_started = False
    await db_session.commit()

    svc = StudentService(db_session)
    result = await svc.ensure_conditional_start_therapy(sample_student, sample_user.id)
    await db_session.commit()

    assert result["ok"] is True
    assert result["already_existed"] is False
    assert result["process_code"] == "start_therapy"
    assert result["instance_id"]

    again = await svc.ensure_conditional_start_therapy(sample_student, sample_user.id)
    await db_session.commit()
    assert again["ok"] is True
    assert again["already_existed"] is True
    assert again["instance_id"] == result["instance_id"]


@pytest.mark.asyncio
async def test_ensure_conditional_rejects_non_conditional(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    persist_admission_type_on_student(sample_student, admission_type="full_admission")
    await db_session.commit()

    svc = StudentService(db_session)
    result = await svc.ensure_conditional_start_therapy(sample_student, sample_user.id)
    assert result["ok"] is False
    assert result["error"] == "only_conditional"


@pytest.mark.asyncio
async def test_intro_second_therapy_check_failed_for_conditional_without_therapist(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "intro_second_semester_registration.json")
    await db_session.commit()

    persist_admission_type_on_student(
        sample_student, admission_type=ADMISSION_CONDITIONAL_THERAPY
    )
    sample_student.therapy_started = False
    sample_student.therapist_id = None
    extra = dict(sample_student.extra_data or {})
    extra["has_active_therapist"] = False
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="intro_second_semester_registration",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="system",
        initial_context={
            "admission_type": ADMISSION_CONDITIONAL_THERAPY,
            "has_active_therapist": False,
        },
    )
    await db_session.commit()

    svc = StudentService(db_session)
    to_state = await svc.advance_intro_second_eligibility(instance.id, sample_user.id)
    await db_session.commit()

    assert to_state == "therapy_check_failed"
    inst = await engine.get_process_instance(instance.id)
    assert inst.current_state_code == "therapy_check_failed"


@pytest.mark.asyncio
async def test_intro_second_eligible_when_conditional_has_therapist(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "intro_second_semester_registration.json")
    await db_session.commit()

    persist_admission_type_on_student(
        sample_student, admission_type=ADMISSION_CONDITIONAL_THERAPY
    )
    sample_student.therapy_started = True
    extra = dict(sample_student.extra_data or {})
    extra["has_active_therapist"] = True
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="intro_second_semester_registration",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="system",
        initial_context={
            "admission_type": ADMISSION_CONDITIONAL_THERAPY,
            "has_active_therapist": True,
        },
    )
    await db_session.commit()

    svc = StudentService(db_session)
    to_state = await svc.advance_intro_second_eligibility(instance.id, sample_user.id)
    await db_session.commit()

    assert to_state == "course_selection"


@pytest.mark.asyncio
async def test_introductory_term_end_blocks_conditional_without_therapy(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "introductory_term_end.json")
    await db_session.commit()

    persist_admission_type_on_student(
        sample_student, admission_type=ADMISSION_CONDITIONAL_THERAPY
    )
    sample_student.therapy_started = False
    sample_student.therapist_id = None
    extra = dict(sample_student.extra_data or {})
    extra["has_active_therapist"] = False
    extra["lms"] = {
        "enrolled_courses": [
            {
                "code": "intro_1",
                "course_name": "درس آشنایی ۱",
                "units": 2,
                "numeric_grade": 15,
                "pass_fail_status": "قبول",
            },
        ],
    }
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    # start_process already auto-advances; refresh after commit
    instance = await engine.start_process(
        process_code="introductory_term_end",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="system",
    )
    await db_session.commit()
    instance = await engine.get_process_instance(instance.id)

    assert instance.current_state_code == "therapy_blocked"
    gates = (sample_student.extra_data or {}).get("gates") or {}
    # refresh student for gate flag written by action
    await db_session.refresh(sample_student)
    gates = (sample_student.extra_data or {}).get("gates") or {}
    assert gates.get("next_term_registration_blocked") is True
