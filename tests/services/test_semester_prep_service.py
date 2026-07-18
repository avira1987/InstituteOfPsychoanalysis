"""Tests for semester preparation institute workflow."""

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_service import (
    FALL_PREP,
    WINTER_PREP,
    ensure_fall_prep_started,
    get_active_prep_instance,
    get_or_start_prep_instance,
    should_auto_start_winter,
)


@pytest.mark.asyncio
async def test_ensure_institute_operational_student_idempotent(db_session: AsyncSession):
    a = await ensure_institute_operational_student(db_session)
    b = await ensure_institute_operational_student(db_session)
    assert a.id == b.id
    assert a.student_code == "INST-OPS"


@pytest.mark.asyncio
async def test_get_or_start_fall_prep_idempotent(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst1, created1 = await get_or_start_prep_instance(
        db_session,
        FALL_PREP,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    assert created1 is True
    assert inst1.current_state_code == "calendar_entry"
    ctx = dict(inst1.context_data or {})
    assert ctx.get("calendar_sla_deadline_at")

    inst2, created2 = await get_or_start_prep_instance(
        db_session,
        FALL_PREP,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    assert created2 is False
    assert inst2.id == inst1.id


@pytest.mark.asyncio
async def test_winter_requires_fall_published(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    with pytest.raises(ValueError, match="fall_semester_preparation"):
        await get_or_start_prep_instance(
            db_session,
            WINTER_PREP,
            actor_id=sample_user.id,
            actor_role="admin",
        )


@pytest.mark.asyncio
async def test_should_auto_start_winter_within_window(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    anchor = await ensure_institute_operational_student(db_session)
    engine = StateMachineEngine(db_session)
    fall = await engine.start_process(
        process_code=FALL_PREP,
        student_id=anchor.id,
        actor_id=sample_user.id,
        actor_role="admin",
        initial_context={
            "winter_start_date": (date.today() + timedelta(days=10)).isoformat(),
        },
    )
    fall.is_completed = True
    fall.current_state_code = "published"
    fall.completed_at = datetime.now(timezone.utc)
    await db_session.commit()

    assert await should_auto_start_winter(db_session, today=date.today()) is True
    assert await get_active_prep_instance(db_session, WINTER_PREP) is None


@pytest.mark.asyncio
async def test_ensure_fall_prep_started(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    hit = await ensure_fall_prep_started(db_session, actor_id=sample_user.id, actor_role="admin")
    assert hit["process_code"] == FALL_PREP
    assert hit["created"] is True


@pytest.mark.asyncio
async def test_build_prep_status_includes_step_sla_deadline(db_session: AsyncSession, sample_user):
    from app.services.semester_prep_service import build_prep_status

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    await db_session.commit()

    status = await build_prep_status(db_session)
    entry = status["processes"][FALL_PREP]
    assert entry["active"] is True
    assert entry.get("sla_deadline_at")
    assert entry.get("calendar_sla_deadline_at")
    assert "اعضای کمیته دروس" in (entry.get("sla_warning_recipients_fa") or [])


@pytest.mark.asyncio
async def test_build_prep_status_tuition_sla_after_transition(db_session: AsyncSession, sample_user):
    from app.services.semester_prep_service import build_prep_status

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    engine = StateMachineEngine(db_session)
    await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="calendar_submitted",
        actor_id=sample_user.id,
        actor_role="admin",
    )
    await db_session.commit()

    status = await build_prep_status(db_session)
    entry = status["processes"][FALL_PREP]
    assert entry["current_state"] == "tuition_entry"
    assert entry.get("sla_deadline_at")
    assert "مدیر آموزش" in (entry.get("sla_warning_recipients_fa") or [])


@pytest.mark.asyncio
async def test_apply_pre_filled_from_fall_courses(db_session: AsyncSession, sample_user):
    from sqlalchemy.orm.attributes import flag_modified

    from app.services.semester_prep_service import (
        FALL_PREP,
        WINTER_PREP,
        apply_pre_filled_fields,
        get_or_start_prep_instance,
    )

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    fall, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    sample_courses = [{"code": "PSY101", "title_fa": "روانشناسی"}]
    ctx = dict(fall.context_data or {})
    ctx["courses_winter"] = sample_courses
    fall.context_data = ctx
    flag_modified(fall, "context_data")
    fall.is_completed = True
    fall.current_state_code = "published"
    fall.completed_at = datetime.now(timezone.utc)
    await db_session.commit()

    merged = await apply_pre_filled_fields(
        db_session,
        WINTER_PREP,
        "course_list_review",
        {},
    )
    assert merged.get("courses") == sample_courses


def test_apply_course_finalization_prefill_from_fall_course_lists():
    from app.services.semester_prep_service import (
        FALL_PREP,
        _apply_course_finalization_prefill,
    )

    draft_fall = [
        {
            "course_name": "تئوری ۱",
            "track": "آشنایی",
            "proposed_day": "شنبه",
            "proposed_time": "18:00",
            "instructor": "دکتر الف",
            "teaching_assistant": "خانم ب",
        }
    ]
    draft_winter = [
        {
            "course_name": "عملی ۲",
            "track": "جامع",
            "day": "دوشنبه",
            "time": "17:30",
            "instructor": "دکتر ج",
        }
    ]
    ctx = {"courses_fall": draft_fall, "courses_winter": draft_winter}
    merged = _apply_course_finalization_prefill(FALL_PREP, "course_finalization", ctx)
    assert merged["courses_finalized_fall"][0]["course_name"] == "تئوری ۱"
    assert merged["courses_finalized_fall"][0]["day"] == "شنبه"
    assert merged["courses_finalized_fall"][0]["time"] == "18:00"
    assert merged["courses_finalized_winter"][0]["course_name"] == "عملی ۲"
    assert merged["courses_finalized_winter"][0]["day"] == "دوشنبه"


def test_apply_course_finalization_prefill_over_placeholder_rows():
    from app.services.semester_prep_service import (
        FALL_PREP,
        _apply_course_finalization_prefill,
    )

    draft_fall = [
        {
            "course_name": "تئوری ۱",
            "track": "آشنایی",
            "proposed_day": "شنبه",
            "proposed_time": "18:00",
            "instructor": "دکتر الف",
        }
    ]
    ctx = {
        "courses_fall": draft_fall,
        "courses_finalized_fall": [
            {
                "course_name": "",
                "track": "",
                "day": "",
                "time": "",
                "instructor": "",
                "teaching_assistant": "",
                "classroom_location": "",
                "instructor_coordinated": False,
            }
        ],
    }
    merged = _apply_course_finalization_prefill(FALL_PREP, "course_finalization", ctx)
    assert merged["courses_finalized_fall"][0]["course_name"] == "تئوری ۱"
    assert merged["courses_finalized_fall"][0]["day"] == "شنبه"


@pytest.mark.asyncio
async def test_build_prep_status_after_rollback_from_published(
    db_session: AsyncSession, sample_user
):
    """پس از rollback از published، status باید فرایند را فعال با current_state قبلی برگرداند."""
    from app.services.semester_prep_service import build_prep_status

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    engine = StateMachineEngine(db_session)
    triggers = [
        "calendar_submitted",
        "tuition_submitted",
        "license_reviewed",
        "course_list_submitted",
        "courses_finalized",
        "marketing_started",
        "interviewers_assigned",
        "interview_times_set",
    ]
    for trigger in triggers:
        result = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event=trigger,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        assert result.success is True, f"transition {trigger} failed: {result.error}"
        await db_session.commit()

    inst = await engine.get_process_instance(inst.id)
    assert inst.current_state_code == "published"
    assert inst.is_completed is True

    status_before = await build_prep_status(db_session)
    entry_before = status_before["processes"][FALL_PREP]
    assert entry_before["active"] is False
    assert entry_before.get("completed_current_state") == "published"

    rollback = await engine.rollback_to_previous_state(
        instance_id=inst.id,
        actor_id=sample_user.id,
        actor_role="admin",
        reason="تست بازگشت برای ویرایش",
    )
    assert rollback.success is True
    assert rollback.to_state == "interview_scheduling"
    await db_session.commit()

    inst = await engine.get_process_instance(inst.id)
    assert inst.current_state_code == "interview_scheduling"
    assert inst.is_completed is False

    status_after = await build_prep_status(db_session)
    entry_after = status_after["processes"][FALL_PREP]
    assert entry_after["active"] is True
    assert entry_after["current_state"] == "interview_scheduling"
    assert entry_after.get("completed_current_state") is None
    assert str(entry_after["instance_id"]) == str(inst.id)

    rollback2 = await engine.rollback_to_previous_state(
        instance_id=inst.id,
        actor_id=sample_user.id,
        actor_role="admin",
        reason="تست بازگشت زنجیره‌ای",
    )
    assert rollback2.success is True
    assert rollback2.to_state == "interviewer_assignment"
    await db_session.commit()

    inst = await engine.get_process_instance(inst.id)
    assert inst.current_state_code == "interviewer_assignment"

    status_after2 = await build_prep_status(db_session)
    assert status_after2["processes"][FALL_PREP]["current_state"] == "interviewer_assignment"


@pytest.mark.asyncio
async def test_build_marketing_handoff_diagnostic(db_session: AsyncSession, sample_user):
    from app.meta.student_step_forms import apply_register_to_context
    from app.services.semester_prep_service import (
        build_marketing_handoff_diagnostic,
        get_or_start_prep_instance,
    )
    from sqlalchemy.orm.attributes import flag_modified

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    calendar_values = {
        "fall_start_date": "2026-09-23",
        "fall_end_date": "2026-12-21",
        "winter_start_date": "2026-12-22",
        "winter_end_date": "2027-03-20",
        "registration_payment_window_start": "2026-08-01",
        "registration_payment_window_end": "2026-09-01",
        "intern_interview_deadline": "2026-08-15",
        "teaching_assistant_interview_deadline": "2026-08-20",
        "nowruz_holiday_start": "2027-03-21",
        "nowruz_holiday_end": "2027-04-02",
    }
    inst.context_data = apply_register_to_context(
        dict(inst.context_data or {}), "calendar_entry", calendar_values
    )
    flag_modified(inst, "context_data")
    await db_session.commit()

    diag = await build_marketing_handoff_diagnostic(db_session, process_code=FALL_PREP)
    entry = diag["processes"][FALL_PREP]
    assert entry["active"] is True
    assert entry["submitted_states"]["calendar_entry"] is True
    assert entry["marketing_keys_present"]["fall_start_date"] is True
