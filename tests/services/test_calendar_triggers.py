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
from app.api.auth import get_password_hash
from app.models.operational_models import InterviewSlot, ProcessInstance, User
import app.services.calendar_triggers as calendar_triggers_mod
from app.services.calendar_triggers import run_calendar_trigger_pass
from app.services.fee_determination_runner import sweep_stuck_fee_determination_triggered

CALENDAR_TRIGGER_SUMMARY_KEYS = (
    "at",
    "payment_timeout",
    "session_payment_sla_reminders",
    "session_payment_autostart_unpaid",
    "send_return_reminder",
    "return_deadline_passed",
    "session_time_reached_attendance",
    "session_time_reached_supervision_50h",
    "installment_due_intro_second_semester",
    "therapist_did_not_record_attendance",
    "interview_slot_reminders",
    "interview_booking_payment_deadline_expiry",
    "interview_time_reached_advance",
    "interview_recurring_slot_generation",
    "start_therapy_sla_reminders",
    "extra_session_sla_reminders",
    "therapy_session_increase_sla_reminders",
    "therapy_session_increase_student_response_reminders",
    "fee_determination_stuck_sweep",
    "fired_total",
)


@pytest.mark.asyncio
async def test_payment_timeout_after_sla_window(
    db_session: AsyncSession, sample_student, sample_user
):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
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
    await load_rules(db_session)
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
    await load_rules(db_session)
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


def test_calendar_triggers_resolves_fee_sweep_import():
    """رگرسیون: run_calendar_trigger_pass نباید NameError برای sweep بدهد."""
    assert calendar_triggers_mod.sweep_stuck_fee_determination_triggered is sweep_stuck_fee_determination_triggered


@pytest.mark.asyncio
async def test_run_calendar_trigger_pass_summary_has_all_keys(db_session: AsyncSession):
    summary = await run_calendar_trigger_pass(db_session)
    missing = [k for k in CALENDAR_TRIGGER_SUMMARY_KEYS if k not in summary]
    assert not missing, f"missing summary keys: {missing}"


@pytest.mark.asyncio
async def test_fee_determination_stuck_sweep_via_calendar_pass(
    db_session: AsyncSession, sample_student, sample_user
):
    """نمونهٔ گیرکرده در triggered باید در پاس تقویمی جمع‌زده شود."""
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "fee_determination.json")
    await db_session.commit()

    oid = uuid.uuid4()
    inst = ProcessInstance(
        id=oid,
        process_code="fee_determination",
        student_id=sample_student.id,
        started_by=sample_user.id,
        current_state_code="triggered",
        context_data={"student_on_leave": True},
    )
    db_session.add(inst)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    assert len(summary["fee_determination_stuck_sweep"]) >= 1
    row = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == oid))
    ).scalars().first()
    assert row.is_completed is True
    assert row.current_state_code == "excluded"


@pytest.mark.asyncio
async def test_fired_total_includes_recurring_slot_generation(
    db_session: AsyncSession,
):
    """fired_total باید اسلات‌های ساخته‌شده از Rule تکراری را هم بشمارد."""
    from app.api.auth import get_password_hash
    from app.models.operational_models import InterviewSlotRecurringRule, User

    uid = uuid.uuid4()
    iv = User(
        id=uid,
        username=f"iv_ft_{uuid.uuid4().hex[:8]}",
        email=f"iv_ft_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبه‌گر fired_total",
        role="interviewer",
    )
    db_session.add(iv)
    await db_session.flush()

    from zoneinfo import ZoneInfo

    tehran_today = datetime.now(ZoneInfo("Asia/Tehran")).date()
    weekday = tehran_today.weekday()

    rule = InterviewSlotRecurringRule(
        id=uuid.uuid4(),
        interviewer_user_id=uid,
        days_of_week=[weekday],
        start_local_time=datetime.strptime("10:00", "%H:%M").time(),
        end_local_time=datetime.strptime("11:00", "%H:%M").time(),
        mode="in_person",
        location_fa="سالن",
        is_active=True,
        horizon_days=7,
    )
    db_session.add(rule)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    created = int(summary["interview_recurring_slot_generation"].get("created_total") or 0)
    assert created >= 1
    assert summary["fired_total"] >= created


@pytest.mark.asyncio
async def test_interview_slot_reminder_sends_before_start(
    db_session: AsyncSession,
    sample_student,
    sample_student_user,
    monkeypatch,
):
    """یادآوری مصاحبه ~۲ ساعت قبل از شروع اسلات رزرو قطعی."""
    sample_student_user.phone = "09121112233"
    await db_session.flush()
    sent: list[tuple[str, str, str]] = []

    async def capture_send(ntype, template, contact, context=None):
        from app.services.notification_service import NotificationResult

        sent.append((ntype, template, contact))
        return NotificationResult(True, ntype, contact, message=template)

    monkeypatch.setattr(
        "app.services.calendar_triggers.notification_service.send_notification",
        capture_send,
    )
    t0 = datetime.now(timezone.utc) + timedelta(hours=1, minutes=30)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="online",
        meeting_link="https://meet.test/rem",
        assigned_student_id=sample_student.id,
        booking_payment_deadline_at=None,
        reminder_sent_at=None,
    )
    db_session.add(slot)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.refresh(slot)

    assert len(summary.get("interview_slot_reminders") or []) >= 1
    assert slot.reminder_sent_at is not None
    assert any(t[1] == "interview_reminder_applicant_online" for t in sent)


@pytest.mark.asyncio
async def test_interview_slot_reminder_includes_interviewer(
    db_session: AsyncSession,
    sample_student,
    sample_student_user,
    monkeypatch,
):
    sample_student_user.phone = "09124445566"
    iv = User(
        id=uuid.uuid4(),
        username=f"iv_rem_{uuid.uuid4().hex[:8]}",
        email=f"iv_rem_{uuid.uuid4().hex[:8]}@test.com",
        hashed_password=get_password_hash("x"),
        full_name_fa="مصاحبه‌گر یادآوری",
        role="interviewer",
        phone="09127778899",
    )
    db_session.add(iv)
    await db_session.flush()

    sent_templates: list[str] = []

    async def capture_send(ntype, template, contact, context=None):
        from app.services.notification_service import NotificationResult

        sent_templates.append(template)
        return NotificationResult(True, ntype, contact, message=template)

    monkeypatch.setattr(
        "app.services.calendar_triggers.notification_service.send_notification",
        capture_send,
    )
    t0 = datetime.now(timezone.utc) + timedelta(hours=1)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=t0,
        ends_at=t0 + timedelta(hours=1),
        mode="in_person",
        location_fa="سالن B",
        assigned_student_id=sample_student.id,
        interviewer_user_id=iv.id,
        booking_payment_deadline_at=None,
    )
    db_session.add(slot)
    await db_session.commit()

    await run_calendar_trigger_pass(db_session)

    assert "interview_reminder_applicant_inperson" in sent_templates
    assert "interview_reminder_interviewer_inperson" in sent_templates


@pytest.mark.asyncio
async def test_advance_due_interview_interviews_moves_intro_reg_to_completed(
    db_session: AsyncSession,
    sample_student,
    sample_user,
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
        actor_role="applicant",
    )
    inst = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    inst.current_state_code = "interview_payment_confirmed"
    await db_session.flush()

    past = datetime.now(timezone.utc) - timedelta(hours=2)
    slot = InterviewSlot(
        id=uuid.uuid4(),
        starts_at=past,
        ends_at=past + timedelta(hours=1),
        mode="online",
        meeting_link="https://example.test/meet",
        assigned_student_id=sample_student.id,
        assigned_instance_id=inst.id,
        booking_payment_deadline_at=None,
    )
    db_session.add(slot)
    await db_session.commit()

    summary = await run_calendar_trigger_pass(db_session)
    await db_session.commit()

    advances = summary.get("interview_time_reached_advance") or []
    assert len(advances) >= 1
    assert advances[0].get("success") is True

    inst2 = (
        await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
    ).scalars().first()
    assert inst2.current_state_code == "interview_completed"
