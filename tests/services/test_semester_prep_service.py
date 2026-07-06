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
