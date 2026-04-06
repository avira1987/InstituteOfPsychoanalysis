"""تست تریگرهای تقویمی (payment_timeout، مرخصی، حضور)."""

import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance
from app.services.calendar_triggers import run_calendar_trigger_pass


@pytest.mark.asyncio
async def test_payment_timeout_after_sla_window(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "session_payment.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="session_payment",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    await db_session.commit()

    inst = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    inst.current_state_code = "awaiting_payment"
    inst.last_transition_at = datetime.now(timezone.utc) - timedelta(hours=100)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    assert len(summary["payment_timeout"]) >= 1
    inst2 = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    assert inst2.current_state_code == "payment_failed"


@pytest.mark.asyncio
async def test_send_return_reminder_when_due(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "educational_leave.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="educational_leave",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    instance.context_data = {
        "return_reminder_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
    }
    instance.current_state_code = "on_leave"
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    assert len(summary["send_return_reminder"]) >= 1
    inst = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    assert inst.current_state_code == "return_reminder_sent"


@pytest.mark.asyncio
async def test_return_deadline_passed(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "educational_leave.json")
    await load_process(db_session, processes_dir / "violation_registration.json")
    await db_session.commit()

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code="educational_leave",
        student_id=sample_student.id,
        actor_id=sample_user.id,
        actor_role="student",
    )
    instance.context_data = {
        "return_deadline_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }
    instance.current_state_code = "return_reminder_sent"
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    assert len(summary["return_deadline_passed"]) >= 1
    inst = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    assert inst.current_state_code == "violation_registered"


@pytest.mark.asyncio
async def test_installment_due_intro_second_semester(
    db_session: AsyncSession, sample_student, sample_user
):
    """سررسید قسط: ``registration_complete`` + ``next_installment_due_at`` گذشته → ``installment_overdue``."""
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "intro_second_semester_registration.json")
    await db_session.commit()

    oid = uuid.uuid4()
    inst = ProcessInstance(
        id=oid,
        process_code="intro_second_semester_registration",
        student_id=sample_student.id,
        started_by=sample_user.id,
        current_state_code="registration_complete",
        context_data={
            "payment_method": "installment",
            "pending_installments_remaining": 2,
            "next_installment_due_at": (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat(),
        },
    )
    db_session.add(inst)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    assert len(summary["installment_due_intro_second_semester"]) >= 1
    row = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == oid))
    ).scalars().first()
    assert row.current_state_code == "installment_overdue"


@pytest.mark.asyncio
async def test_installment_due_not_fired_when_due_date_future(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "intro_second_semester_registration.json")
    await db_session.commit()

    oid = uuid.uuid4()
    inst = ProcessInstance(
        id=oid,
        process_code="intro_second_semester_registration",
        student_id=sample_student.id,
        started_by=sample_user.id,
        current_state_code="registration_complete",
        context_data={
            "payment_method": "installment",
            "pending_installments_remaining": 2,
            "next_installment_due_at": (datetime.now(timezone.utc).date() + timedelta(days=10)).isoformat(),
        },
    )
    db_session.add(inst)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    assert len(summary["installment_due_intro_second_semester"]) == 0


@pytest.mark.asyncio
async def test_therapist_did_not_record_after_24h(
    db_session: AsyncSession, sample_student, sample_user
):
    """پس از ۲۴ ساعت از نیمه‌شب روز ``session_date``، تریگر خودکار ثبت‌نکردن درمانگر."""
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "attendance_tracking.json")
    await db_session.commit()

    oid = uuid.uuid4()
    past = datetime.now(timezone.utc).date() - timedelta(days=3)
    inst = ProcessInstance(
        id=oid,
        process_code="attendance_tracking",
        student_id=sample_student.id,
        started_by=sample_user.id,
        current_state_code="therapist_recording",
        context_data={
            "session_date": past.isoformat(),
            "session_paid": True,
            "student_on_leave": False,
            "session_cancelled": False,
        },
    )
    db_session.add(inst)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    assert len(summary["therapist_did_not_record_attendance"]) >= 1
    row = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == oid))
    ).scalars().first()
    assert row.current_state_code == "site_manager_pending"


@pytest.mark.asyncio
async def test_therapist_recording_no_auto_trigger_within_24h(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "attendance_tracking.json")
    await db_session.commit()

    oid = uuid.uuid4()
    today = datetime.now(timezone.utc).date()
    inst = ProcessInstance(
        id=oid,
        process_code="attendance_tracking",
        student_id=sample_student.id,
        started_by=sample_user.id,
        current_state_code="therapist_recording",
        context_data={
            "session_date": today.isoformat(),
            "session_paid": True,
            "student_on_leave": False,
            "session_cancelled": False,
        },
    )
    db_session.add(inst)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    assert len(summary["therapist_did_not_record_attendance"]) == 0


@pytest.mark.asyncio
async def test_run_calendar_trigger_pass_summary_has_all_keys(db_session: AsyncSession):
    summary = await run_calendar_trigger_pass(db_session)
    for key in (
        "at",
        "payment_timeout",
        "send_return_reminder",
        "return_deadline_passed",
        "session_time_reached_attendance",
        "session_time_reached_supervision_50h",
        "installment_due_intro_second_semester",
        "therapist_did_not_record_attendance",
        "fired_total",
    ):
        assert key in summary
