"""Tests for introductory registration readiness gate."""

import pytest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import InvalidTransitionError, StateMachineEngine
from app.meta.course_selection_validation import validate_intro_term1_selected_courses
from app.meta.seed import load_process
from app.models.operational_models import InstituteCalendar
from app.services.registration_readiness_service import check_intro_registration_gate
from app.services.term_course_offering_service import resolve_course_code_from_name
from app.utils.shamsi_calendar_utils import tehran_day_end_utc, tehran_day_start_utc
from app.services.student_service import StudentService
from tests.helpers.registration_gate_fixture import open_intro_registration_gate


def test_resolve_course_code_from_name():
    assert resolve_course_code_from_name("تئوری روانکاوی ۱") == "theory_psychoanalysis_1"
    assert resolve_course_code_from_name("theory_psychoanalysis_3") == "theory_psychoanalysis_3"


@pytest.mark.asyncio
async def test_gate_open_on_last_day_of_date_only_window(db_session: AsyncSession, monkeypatch):
    from tests.helpers.registration_gate_fixture import open_intro_registration_gate

    await open_intro_registration_gate(db_session)
    cal_row = await db_session.execute(
        __import__("sqlalchemy").select(InstituteCalendar).where(InstituteCalendar.is_active.is_(True))
    )
    cal = cal_row.scalars().first()
    assert cal is not None
    window_start = date(2026, 8, 1)
    window_end = date(2026, 9, 1)
    cal.registration_open_at = tehran_day_start_utc(window_start)
    cal.registration_deadline_at = tehran_day_end_utc(window_end)
    cal.extra_data = {
        **(cal.extra_data or {}),
        "registration_payment_window_start": window_start.isoformat(),
        "registration_payment_window_end": window_end.isoformat(),
    }
    await db_session.commit()

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            base = tehran_day_end_utc(window_end) - timedelta(hours=2)
            return base if tz else base.replace(tzinfo=None)

    monkeypatch.setattr("app.services.registration_readiness_service.datetime", _FixedDatetime)
    gate = await check_intro_registration_gate(db_session)
    assert gate.allowed is True
    assert gate.in_registration_window is True


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
        "available_courses": ["theory_psychoanalysis_1", "theory_psychoanalysis_2"],
        "available_course_options": [
            {"value": "theory_psychoanalysis_1", "label_fa": "تئوری روانکاوی ۱"},
            {"value": "theory_psychoanalysis_2", "label_fa": "تئوری روانکاوی ۲"},
        ],
    }
    ok, err = validate_intro_term1_selected_courses(ctx, ["theory_psychoanalysis_1"])
    assert ok is True
    ok2, err2 = validate_intro_term1_selected_courses(ctx, ["theory_psychoanalysis_5"])
    assert ok2 is False
