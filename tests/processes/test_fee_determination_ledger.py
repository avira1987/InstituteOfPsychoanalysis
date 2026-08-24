"""Slice 1 / Phase C: fee_determination ledger outcomes from attendance_tracking."""

from datetime import date, timedelta
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import FinancialRecord, ProcessInstance, TherapySession
from app.services.fee_determination_runner import (
    SYSTEM_ACTOR_ID,
    infer_session_cancelled_by,
    provider_cancel_flag,
)
from app.services.payment_service import LEDGER_THERAPY, PaymentService


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


async def _load(db: AsyncSession) -> StateMachineEngine:
    await load_rules(db)
    await load_process(db, PROCESSES_DIR / "attendance_tracking.json")
    await load_process(db, PROCESSES_DIR / "fee_determination.json")
    await db.commit()
    return StateMachineEngine(db)


async def _make_session(db, student, *, paid: bool, notes: str | None = None, cancelled: bool = False):
    ts = TherapySession(
        student_id=student.id,
        session_date=date.today() - timedelta(days=1),
        status="cancelled" if cancelled else "scheduled",
        is_extra=False,
        payment_status="paid" if paid else "pending",
        notes=notes,
        amount=float(PaymentService.DEFAULT_SESSION_FEE),
    )
    db.add(ts)
    await db.flush()
    return ts


async def _fee_child(db, parent_id, student_id) -> ProcessInstance:
    rows = (
        await db.execute(
            select(ProcessInstance).where(
                ProcessInstance.student_id == student_id,
                ProcessInstance.process_code == "fee_determination",
            )
        )
    ).scalars().all()
    for row in rows:
        if (row.context_data or {}).get("parent_instance_id") == str(parent_id):
            return row
    assert rows, "fee_determination child was not started"
    return rows[-1]


async def _ledger(db, student_id) -> list[FinancialRecord]:
    return list(
        (
            await db.execute(
                select(FinancialRecord).where(FinancialRecord.student_id == student_id)
            )
        ).scalars().all()
    )


async def _run_unpaid_calendar(engine, db, student, sample_user) -> ProcessInstance:
    ts = await _make_session(db, student, paid=False)
    parent = await engine.start_process(
        process_code="attendance_tracking",
        student_id=student.id,
        actor_id=sample_user.id,
        actor_role="system",
        initial_context={"therapy_session_id": str(ts.id)},
    )
    await db.commit()
    result = await engine.execute_transition(
        instance_id=parent.id,
        trigger_event="session_time_reached",
        actor_id=SYSTEM_ACTOR_ID,
        actor_role="system",
    )
    await db.commit()
    assert result.success is True, result.error
    parent = await engine.get_process_instance(parent.id)
    assert parent.current_state_code == "auto_absence_unpaid"
    return await _fee_child(db, parent.id, student.id)


async def _run_therapist_unexcused(engine, db, student, sample_user) -> ProcessInstance:
    ts = await _make_session(db, student, paid=True)
    parent = await engine.start_process(
        process_code="attendance_tracking",
        student_id=student.id,
        actor_id=sample_user.id,
        actor_role="system",
        initial_context={"therapy_session_id": str(ts.id)},
    )
    await db.commit()
    r1 = await engine.execute_transition(
        instance_id=parent.id,
        trigger_event="session_time_reached",
        actor_id=SYSTEM_ACTOR_ID,
        actor_role="system",
    )
    await db.commit()
    assert r1.success is True, r1.error
    parent = await engine.get_process_instance(parent.id)
    assert parent.current_state_code == "therapist_recording"

    r2 = await engine.execute_transition(
        instance_id=parent.id,
        trigger_event="student_absent",
        actor_id=sample_user.id,
        actor_role="therapist",
    )
    await db.commit()
    assert r2.success is True, r2.error

    r3 = await engine.execute_transition(
        instance_id=parent.id,
        trigger_event="absence_unexcused",
        actor_id=SYSTEM_ACTOR_ID,
        actor_role="system",
        payload={"absence_excused": False},
    )
    await db.commit()
    assert r3.success is True, r3.error
    parent = await engine.get_process_instance(parent.id)
    assert parent.current_state_code in ("unexcused_absence", "quota_exceeded")
    return await _fee_child(db, parent.id, student.id)


class TestCancelledByAlignment:
    def test_student_cancel_notes_are_not_provider(self):
        by = infer_session_cancelled_by("[student_session_cancellation:abc]")
        assert by == "student"
        assert provider_cancel_flag(by) is False

    def test_therapist_cancel_notes_are_provider(self):
        by = infer_session_cancelled_by("[therapist_session_cancellation:abc]")
        assert by == "therapist"
        assert provider_cancel_flag(by) is True


@pytest.mark.asyncio
class TestFeeDeterminationLedgerFromAttendance:
    async def test_paid_quota_remaining_writes_credit(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await _load(db_session)
        fee = await _run_therapist_unexcused(engine, db_session, sample_student, sample_user)
        assert fee.current_state_code == "scenario_1_credit_returned"
        rows = await _ledger(db_session, sample_student.id)
        assert len(rows) == 1
        assert rows[0].record_type == "credit"
        assert rows[0].ledger_category == LEDGER_THERAPY
        assert float(rows[0].amount) == float(PaymentService.DEFAULT_SESSION_FEE)
        assert rows[0].reference_id == fee.id

    async def test_unpaid_quota_remaining_has_no_money_row(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await _load(db_session)
        fee = await _run_unpaid_calendar(engine, db_session, sample_student, sample_user)
        assert fee.current_state_code == "scenario_2_no_action"
        rows = await _ledger(db_session, sample_student.id)
        assert rows == []

    async def test_paid_quota_exhausted_writes_absence_fee(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        sample_student.weekly_sessions = 0
        await db_session.flush()
        engine = await _load(db_session)
        fee = await _run_therapist_unexcused(engine, db_session, sample_student, sample_user)
        assert fee.current_state_code == "scenario_3_forfeited"
        rows = await _ledger(db_session, sample_student.id)
        assert len(rows) == 1
        assert rows[0].record_type == "absence_fee"
        assert float(rows[0].amount) == float(PaymentService.DEFAULT_SESSION_FEE)

    @pytest.mark.parametrize("seed_credit", [False, True])
    async def test_unpaid_quota_exhausted_debt_or_credit_consume(
        self, db_session: AsyncSession, sample_student, sample_user, seed_credit: bool
    ):
        sample_student.weekly_sessions = 0
        await db_session.flush()
        if seed_credit:
            pay = PaymentService(db_session)
            await pay.process_refund(
                student_id=sample_student.id,
                amount=float(PaymentService.DEFAULT_SESSION_FEE),
                reason="seed credit",
                category=LEDGER_THERAPY,
            )
            await db_session.flush()
        engine = await _load(db_session)
        fee = await _run_unpaid_calendar(engine, db_session, sample_student, sample_user)
        assert fee.current_state_code == "scenario_4_debt_created"
        rows = await _ledger(db_session, sample_student.id)
        debts = [r for r in rows if r.record_type == "debt"]
        assert len(debts) == 1
        assert float(debts[0].amount) == float(PaymentService.DEFAULT_SESSION_FEE)
        assert debts[0].reference_id == fee.id
        if seed_credit:
            assert (fee.context_data or {}).get("fee_settlement_mode") == "from_existing_credit_balance"
            bal = await PaymentService(db_session).get_student_balance(
                sample_student.id, category=LEDGER_THERAPY
            )
            assert float(bal["balance"]) == 0.0
        else:
            assert (fee.context_data or {}).get("fee_settlement_mode") == "new_debt"

    async def test_provider_cancel_is_excluded_without_ledger(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await _load(db_session)
        ts = await _make_session(
            db_session,
            sample_student,
            paid=True,
            cancelled=True,
            notes="[therapist_session_cancellation:x]",
        )
        fee = await engine.start_process(
            process_code="fee_determination",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
            initial_context={
                "therapy_session_id": str(ts.id),
                "cancelled_by": "therapist",
                "parent_instance_id": "attendance-parent",
            },
        )
        await db_session.flush()
        from app.services.fee_determination_runner import complete_fee_determination_instance

        out = await complete_fee_determination_instance(db_session, fee.id)
        await db_session.commit()
        fee = await engine.get_process_instance(fee.id)
        assert fee.current_state_code == "excluded"
        assert out.get("completed") is True
        assert await _ledger(db_session, sample_student.id) == []

    async def test_student_cancel_notes_do_not_exclude(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await _load(db_session)
        ts = await _make_session(
            db_session,
            sample_student,
            paid=False,
            cancelled=True,
            notes="[student_session_cancellation:x]",
        )
        fee = await engine.start_process(
            process_code="fee_determination",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
            initial_context={
                "therapy_session_id": str(ts.id),
                "cancelled_by": "student",
                "session_paid": False,
                "student_on_leave": False,
            },
        )
        await db_session.flush()
        from app.services.fee_determination_runner import complete_fee_determination_instance

        await complete_fee_determination_instance(db_session, fee.id)
        await db_session.commit()
        fee = await engine.get_process_instance(fee.id)
        assert fee.current_state_code == "scenario_2_no_action"
        assert await _ledger(db_session, sample_student.id) == []
