"""تست موتور زمان‌بندی فرایند (process_scheduler)."""

import uuid
from datetime import datetime, timezone, timedelta, date
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import InstituteCalendar, ProcessInstance, Student
from app.services.institute_calendar_service import upsert_active_calendar, sync_term_dates_to_students
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.process_scheduler import (
    dispatch_installment_overdue,
    dispatch_scheduled_reminders,
    dispatch_generic_sla_triggers,
    dispatch_academic_term_batch,
    dispatch_semester_prep_starts,
    run_process_scheduler_pass,
)
from app.utils.shamsi_calendar_utils import is_farvardin_15_20


@pytest.mark.asyncio
async def test_dispatch_installment_overdue_introductory(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "introductory_course_registration.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    inst = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    inst.current_state_code = "registration_complete"
    inst.context_data = {
        "pending_installments_remaining": 2,
        "next_installment_due_at": (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
    }
    flag_modified(inst, "context_data")
    await db_session.commit()

    hits = await dispatch_installment_overdue(db_session, datetime.now(timezone.utc).date())
    await db_session.commit()

    assert len(hits) >= 1
    inst2 = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    assert inst2.current_state_code == "installment_overdue"


@pytest.mark.asyncio
async def test_dispatch_installment_overdue_idempotent(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "intro_second_semester_registration.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="intro_second_semester_registration",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    due = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
    inst = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    inst.current_state_code = "registration_complete"
    inst.context_data = {
        "pending_installments_remaining": 1,
        "next_installment_due_at": due,
    }
    flag_modified(inst, "context_data")
    await db_session.commit()

    today = datetime.now(timezone.utc).date()
    first = await dispatch_installment_overdue(db_session, today)
    await db_session.commit()
    second = await dispatch_installment_overdue(db_session, today)
    assert len(first) >= 1
    assert len(second) == 0


@pytest.mark.asyncio
async def test_dispatch_scheduled_reminders_sends_and_marks_sent(
    db_session: AsyncSession, sample_student, sample_student_user
):
    extra = dict(sample_student.extra_data or {})
    extra["scheduled_reminders"] = [
        {
            "id": "r1",
            "type": "installment",
            "due_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "template": "installment_due_reminder",
            "sent": False,
        }
    ]
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    hits = await dispatch_scheduled_reminders(db_session, datetime.now(timezone.utc))
    await db_session.commit()

    assert len(hits) >= 1
    st = (await db_session.execute(select(Student).where(Student.id == sample_student.id))).scalars().first()
    rems = (st.extra_data or {}).get("scheduled_reminders") or []
    assert rems[0].get("sent") is True


@pytest.mark.asyncio
async def test_dispatch_scheduled_reminders_skips_cash_instance(
    db_session: AsyncSession, sample_student, sample_student_user
):
    inst = ProcessInstance(
        id=uuid.uuid4(),
        process_code="introductory_course_registration",
        student_id=sample_student.id,
        current_state_code="registration_complete",
        context_data={"payment_method": "cash", "pending_installments_remaining": 0},
    )
    db_session.add(inst)
    extra = dict(sample_student.extra_data or {})
    extra["scheduled_reminders"] = [
        {
            "id": "cash-r1",
            "type": "installment",
            "instance_id": str(inst.id),
            "due_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "template": "installment_reminder",
            "amount_rial": 70000,
            "sent": False,
        }
    ]
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()

    hits = await dispatch_scheduled_reminders(db_session, datetime.now(timezone.utc))
    await db_session.commit()

    assert any(h.get("skipped") for h in hits)
    st = (await db_session.execute(select(Student).where(Student.id == sample_student.id))).scalars().first()
    rems = (st.extra_data or {}).get("scheduled_reminders") or []
    assert rems[0].get("sent") is True
    assert rems[0].get("skipped") is True


@pytest.mark.asyncio
async def test_dispatch_generic_sla_triggers_theory_course(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "theory_course_completion.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="theory_course_completion",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="instructor",
    )
    inst = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    inst.last_transition_at = datetime.now(timezone.utc) - timedelta(days=10)
    await db_session.commit()

    hits = await dispatch_generic_sla_triggers(db_session, datetime.now(timezone.utc))
    await db_session.commit()

    assert len(hits) >= 1
    inst2 = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    assert inst2.current_state_code == "delay_reported"


@pytest.mark.asyncio
async def test_academic_term_batch_evaluation_deadline(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "student_instructor_evaluation.json")
    await db_session.commit()

    now = datetime.now(timezone.utc)
    payload = {
        "term_code": "test-term-eval",
        "term_start_date": date.today(),
        "term_end_date": date.today() + timedelta(days=90),
        "evaluation_open_at": now - timedelta(days=20),
        "evaluation_close_at": now - timedelta(hours=1),
    }
    cal = await upsert_active_calendar(db_session, payload=payload)
    await sync_term_dates_to_students(db_session, cal)

    engine = StateMachineEngine(db_session)
    inst = await engine.start_process(
        process_code="student_instructor_evaluation",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    await db_session.commit()

    hits = await dispatch_academic_term_batch(db_session, now)
    await db_session.commit()

    assert any(h.get("trigger") == "deadline_reached" for h in hits)
    row = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == inst.id))
    ).scalars().first()
    assert row.current_state_code == "evaluation_closed"


@pytest.mark.asyncio
async def test_run_process_scheduler_pass_summary_keys(db_session: AsyncSession):
    summary = await run_process_scheduler_pass(db_session)
    for key in (
        "scheduled_reminders",
        "installment_overdue",
        "generic_sla_triggers",
        "academic_term_batch",
        "student_milestones",
        "start_therapy_week9",
        "lms_session_hooks",
        "semester_prep_starts",
        "scheduler_fired_total",
    ):
        assert key in summary


@pytest.mark.asyncio
async def test_dispatch_semester_prep_starts_farvardin_window(
    db_session: AsyncSession, sample_user
):
    import jdatetime

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()

    sy = jdatetime.date.today().year
    farvardin_day = jdatetime.date(sy, 1, 17).togregorian()
    assert is_farvardin_15_20(farvardin_day)

    hits = await dispatch_semester_prep_starts(db_session, today=farvardin_day)
    assert any(h.get("process_code") == "fall_semester_preparation" for h in hits)

    hits2 = await dispatch_semester_prep_starts(db_session, today=farvardin_day)
    assert not any(h.get("created") for h in hits2)


@pytest.mark.asyncio
async def test_dispatch_semester_prep_starts_winter_window(
    db_session: AsyncSession, sample_user
):
    from datetime import date

    from app.services.semester_prep_service import ensure_winter_prep_started

    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    fall = await engine.start_process(
        process_code="fall_semester_preparation",
        student_id=(await ensure_institute_operational_student(db_session)).id,
        actor_id=sample_user.id,
        actor_role="admin",
    )
    fall.context_data = {
        "winter_start_date": (date.today() + timedelta(days=10)).isoformat(),
    }
    flag_modified(fall, "context_data")
    fall.is_completed = True
    fall.current_state_code = "published"
    fall.completed_at = datetime.now(timezone.utc)
    await db_session.commit()

    today = date.today()
    hits = await dispatch_semester_prep_starts(db_session, today=today)
    assert any(
        h.get("process_code") == "winter_semester_preparation" and h.get("created")
        for h in hits
    )

    hit = await ensure_winter_prep_started(db_session, actor_id=sample_user.id, actor_role="admin")
    assert hit is not None
    assert hit["process_code"] == "winter_semester_preparation"

    hits2 = await dispatch_semester_prep_starts(db_session, today=today)
    assert not any(
        h.get("process_code") == "winter_semester_preparation" and h.get("created")
        for h in hits2
    )
