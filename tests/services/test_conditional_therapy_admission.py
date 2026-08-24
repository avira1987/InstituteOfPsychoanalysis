"""Tests for conditional therapy admission flags, ensure API, term-end chain, term2 gate."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.core.rule_engine import RuleEvaluator
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance, Student
from app.services.action_handler import ActionHandler
from app.services.admission_type_service import (
    ADMISSION_CONDITIONAL_THERAPY,
    ADMISSION_FULL,
    ADMISSION_SINGLE_COURSE,
    CONDITIONAL_THERAPY_TERM2_NOTICE_FA,
    derive_has_active_therapist,
    normalize_admission_type,
    persist_admission_type_on_student,
    should_auto_start_educational_therapy,
    should_show_conditional_therapy_term2_notice,
    term2_blocked_without_active_therapist,
    therapy_deadline_hint_fa,
    therapy_start_applicable,
)
from app.services.introductory_registration_chaining import (
    _persist_admission_from_instance,
)
from app.services.student_service import StudentService

PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


def test_therapy_start_applicable_excludes_single_course():
    assert therapy_start_applicable(ADMISSION_SINGLE_COURSE) is False
    assert therapy_start_applicable("result_single_course") is False
    assert therapy_start_applicable(ADMISSION_CONDITIONAL_THERAPY) is True
    assert therapy_start_applicable(ADMISSION_FULL) is True
    assert therapy_start_applicable(None) is True


def test_student_eligible_for_therapy_rule_rejects_single_course():
    rules_path = (
        Path(__file__).resolve().parent.parent.parent
        / "metadata"
        / "rules"
        / "all_rules.json"
    )
    rules = json.loads(rules_path.read_text(encoding="utf-8"))
    eligible = next(r for r in rules if r["code"] == "student_eligible_for_therapy")
    not_eligible = next(r for r in rules if r["code"] == "student_not_eligible")
    evaluator = RuleEvaluator()

    single_ctx = {
        "student": {
            "course_type": "introductory",
            "term_count": 1,
            "admission_type": "single_course",
            "is_suspended": False,
        },
        "instance": {},
    }
    full_ctx = {
        "student": {
            "course_type": "introductory",
            "term_count": 1,
            "admission_type": "full_admission",
            "is_suspended": False,
        },
        "instance": {},
    }

    assert evaluator.evaluate_rule(eligible, single_ctx).passed is False
    assert evaluator.evaluate_rule(not_eligible, single_ctx).passed is True
    assert evaluator.evaluate_rule(eligible, full_ctx).passed is True
    assert evaluator.evaluate_rule(not_eligible, full_ctx).passed is False


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
async def test_followup_after_intro_skips_start_therapy_for_single_course(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "start_therapy.json")
    await db_session.commit()

    persist_admission_type_on_student(
        sample_student, admission_type=ADMISSION_SINGLE_COURSE
    )
    sample_student.therapy_started = False
    await db_session.commit()

    reg = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="registration_complete",
        is_completed=True,
        context_data={
            "admission_type": ADMISSION_SINGLE_COURSE,
            "interview_result": ADMISSION_SINGLE_COURSE,
        },
        started_by=sample_user.id,
    )
    db_session.add(reg)
    await db_session.commit()

    svc = StudentService(db_session)
    await svc.maybe_start_followup_after_intro_registration(reg)
    await db_session.commit()
    await db_session.refresh(sample_student)
    await db_session.refresh(reg)

    therapy_rows = (
        await db_session.execute(
            select(ProcessInstance).where(
                ProcessInstance.student_id == sample_student.id,
                ProcessInstance.process_code == "start_therapy",
            )
        )
    ).scalars().all()
    assert therapy_rows == []
    extra = sample_student.extra_data or {}
    assert extra.get("primary_instance_id") in (None, "", str(reg.id))
    assert "تک‌درس" in (reg.context_data or {}).get("intro_registration_next_step_fa", "")


@pytest.mark.asyncio
async def test_followup_after_intro_conditional_does_not_force_start_therapy(
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

    reg = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="registration_complete",
        is_completed=True,
        context_data={
            "admission_type": ADMISSION_CONDITIONAL_THERAPY,
            "interview_result": ADMISSION_CONDITIONAL_THERAPY,
        },
        started_by=sample_user.id,
    )
    db_session.add(reg)
    await db_session.commit()

    svc = StudentService(db_session)
    await svc.maybe_start_followup_after_intro_registration(reg)
    await db_session.commit()
    await db_session.refresh(sample_student)
    await db_session.refresh(reg)

    therapy_rows = (
        await db_session.execute(
            select(ProcessInstance).where(
                ProcessInstance.student_id == sample_student.id,
                ProcessInstance.process_code == "start_therapy",
            )
        )
    ).scalars().all()
    assert therapy_rows == []
    assert (sample_student.extra_data or {}).get("primary_instance_id") in (None, "")
    next_step = (reg.context_data or {}).get("intro_registration_next_step_fa", "")
    assert next_step == CONDITIONAL_THERAPY_TERM2_NOTICE_FA

    # کارت اختیاری همچنان می‌تواند فرایند را شروع کند
    ensured = await svc.ensure_conditional_start_therapy(sample_student, sample_user.id)
    await db_session.commit()
    assert ensured["ok"] is True
    assert ensured["instance_id"]


@pytest.mark.asyncio
async def test_followup_after_intro_full_admission_still_starts_therapy(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "start_therapy.json")
    await db_session.commit()

    persist_admission_type_on_student(sample_student, admission_type=ADMISSION_FULL)
    sample_student.therapy_started = False
    sample_student.course_type = "introductory"
    sample_student.term_count = 1
    await db_session.commit()

    reg = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="registration_complete",
        is_completed=True,
        context_data={
            "admission_type": ADMISSION_FULL,
            "interview_result": ADMISSION_FULL,
            "allowed_course_count": 5,
        },
        started_by=sample_user.id,
    )
    db_session.add(reg)
    await db_session.commit()

    svc = StudentService(db_session)
    await svc.maybe_start_followup_after_intro_registration(reg)
    await db_session.commit()
    await db_session.refresh(sample_student)

    therapy_rows = (
        await db_session.execute(
            select(ProcessInstance).where(
                ProcessInstance.student_id == sample_student.id,
                ProcessInstance.process_code == "start_therapy",
            )
        )
    ).scalars().all()
    assert len(therapy_rows) == 1
    primary = (sample_student.extra_data or {}).get("primary_instance_id")
    assert primary == str(therapy_rows[0].id)


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
async def test_intro_second_single_course_without_therapist_allowed(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "intro_second_semester_registration.json")
    await db_session.commit()

    persist_admission_type_on_student(
        sample_student, admission_type=ADMISSION_SINGLE_COURSE
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
            "admission_type": ADMISSION_SINGLE_COURSE,
            "has_active_therapist": False,
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


def test_should_auto_start_educational_therapy_only_full_or_comprehensive():
    assert should_auto_start_educational_therapy(ADMISSION_FULL, "introductory") is True
    assert should_auto_start_educational_therapy(ADMISSION_CONDITIONAL_THERAPY, "introductory") is False
    assert should_auto_start_educational_therapy(ADMISSION_SINGLE_COURSE, "introductory") is False
    assert should_auto_start_educational_therapy(None, "introductory") is False
    assert should_auto_start_educational_therapy(None, "comprehensive") is True


def test_term2_blocked_without_active_therapist_only_conditional():
    assert term2_blocked_without_active_therapist(
        ADMISSION_CONDITIONAL_THERAPY, has_active_therapist=False
    ) is True
    assert term2_blocked_without_active_therapist(
        ADMISSION_CONDITIONAL_THERAPY, has_active_therapist=True
    ) is False
    assert term2_blocked_without_active_therapist(
        ADMISSION_SINGLE_COURSE, has_active_therapist=False
    ) is False
    assert term2_blocked_without_active_therapist(
        ADMISSION_FULL, has_active_therapist=False
    ) is False


@pytest.mark.asyncio
async def test_followup_unknown_intro_admission_does_not_start_therapy(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    await load_rules(db_session)
    await load_process(db_session, PROCESSES_DIR / "start_therapy.json")
    await db_session.commit()

    sample_student.therapy_started = False
    sample_student.course_type = "introductory"
    sample_student.extra_data = {}
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    reg = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="registration_complete",
        is_completed=True,
        context_data={},
        started_by=sample_user.id,
    )
    db_session.add(reg)
    await db_session.commit()

    svc = StudentService(db_session)
    await svc.maybe_start_followup_after_intro_registration(reg)
    await db_session.commit()

    therapy_rows = (
        await db_session.execute(
            select(ProcessInstance).where(
                ProcessInstance.student_id == sample_student.id,
                ProcessInstance.process_code == "start_therapy",
            )
        )
    ).scalars().all()
    assert therapy_rows == []


@pytest.mark.asyncio
async def test_reconcile_cancels_start_therapy_for_single_course(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    persist_admission_type_on_student(
        sample_student, admission_type=ADMISSION_SINGLE_COURSE
    )
    sample_student.therapy_started = False
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="start_therapy",
        student_id=sample_student.id,
        current_state_code="therapist_selection",
        is_completed=False,
        is_cancelled=False,
        context_data={"source": "after_introductory_registration_complete"},
        started_by=sample_user.id,
    )
    db_session.add(inst)
    extra = dict(sample_student.extra_data or {})
    extra["primary_instance_id"] = str(inst.id)
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    svc = StudentService(db_session)
    changed = await svc.reconcile_start_therapy_for_admission(sample_student)
    await db_session.commit()
    await db_session.refresh(inst)
    await db_session.refresh(sample_student)

    assert changed is True
    assert inst.is_cancelled is True
    assert (sample_student.extra_data or {}).get("primary_instance_id") in (None, "")


@pytest.mark.asyncio
async def test_reconcile_unprimaries_forced_start_therapy_for_conditional(
    db_session: AsyncSession, sample_student: Student, sample_user
):
    persist_admission_type_on_student(
        sample_student, admission_type=ADMISSION_CONDITIONAL_THERAPY
    )
    sample_student.therapy_started = False
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="start_therapy",
        student_id=sample_student.id,
        current_state_code="therapist_selection",
        is_completed=False,
        is_cancelled=False,
        context_data={"source": "after_introductory_registration_complete"},
        started_by=sample_user.id,
    )
    db_session.add(inst)
    extra = dict(sample_student.extra_data or {})
    extra["primary_instance_id"] = str(inst.id)
    extra.pop("conditional_therapy_start_opted_in", None)
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    svc = StudentService(db_session)
    changed = await svc.reconcile_start_therapy_for_admission(sample_student)
    await db_session.commit()
    await db_session.refresh(inst)
    await db_session.refresh(sample_student)

    assert changed is True
    assert inst.is_cancelled is False
    assert (sample_student.extra_data or {}).get("primary_instance_id") in (None, "")


def test_conditional_therapy_term2_notice_after_interview_result():
    assert therapy_deadline_hint_fa() == CONDITIONAL_THERAPY_TERM2_NOTICE_FA
    assert therapy_deadline_hint_fa(deadline="1405-06-01") == CONDITIONAL_THERAPY_TERM2_NOTICE_FA
    assert should_show_conditional_therapy_term2_notice(
        process_code="introductory_course_registration",
        state_code="result_conditional_therapy",
        context={},
    ) is True
    assert should_show_conditional_therapy_term2_notice(
        process_code="introductory_course_registration",
        state_code="registration_complete",
        context={"admission_type": ADMISSION_CONDITIONAL_THERAPY},
    ) is True
    assert should_show_conditional_therapy_term2_notice(
        process_code="introductory_course_registration",
        state_code="registration_complete",
        context={"admission_type": ADMISSION_FULL},
    ) is False
    assert should_show_conditional_therapy_term2_notice(
        process_code="introductory_course_registration",
        state_code="application_submitted",
        context={},
    ) is False
