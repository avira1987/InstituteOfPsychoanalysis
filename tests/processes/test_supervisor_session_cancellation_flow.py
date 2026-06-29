"""Test supervisor_session_cancellation as جریان بزرگ (BUILD_TODO item ۲۳ — ه بخش ۲۰: کنسل جلسه توسط سوپروایزر)."""

from datetime import date, timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance
from app.services.supervisor_session_cancellation_service import (
    build_supervisor_cancellation_context,
    get_supervisor_sessions_next_4_weeks,
)


async def _load_cancel_processes(db_session: AsyncSession) -> None:
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_rules(db_session)
    await load_process(db_session, processes_dir / "supervisor_session_cancellation.json")


async def _seed_supervision_session(
    db_session: AsyncSession,
    student_id,
    *,
    paid: bool = True,
) -> ProcessInstance:
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "supervision_50h_completion.json")
    session_date = (date.today() + timedelta(days=7)).isoformat()
    inst = ProcessInstance(
        id=uuid4(),
        process_code="supervision_50h_completion",
        student_id=student_id,
        current_state_code="session_scheduled",
        context_data={
            "session_date": session_date,
            "supervision_session_date": session_date,
            "session_time": "10:00",
            "supervision_session_paid": paid,
        },
    )
    db_session.add(inst)
    await db_session.flush()
    return inst


@pytest.mark.asyncio
class TestSupervisorSessionCancellationFlow:

    async def test_supervisor_session_cancellation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند کنسل جلسه توسط سوپروایزر لود و استارت می‌شود؛ state اول session_selection است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "supervisor_session_cancellation.json"
        assert process_file.exists()

        await load_rules(db_session)
        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervisor_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="supervisor",
        )
        await db_session.commit()

        assert instance.process_code == "supervisor_session_cancellation"
        assert instance.current_state_code == "session_selection"
        assert instance.is_completed is False

    async def test_supervisor_session_cancellation_flow_no_makeup(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان لغو بدون جبرانی: session_selection → makeup_choice → cancelled_no_makeup."""
        await _load_cancel_processes(db_session)
        sup_inst = await _seed_supervision_session(db_session, sample_student.id)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervisor_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="supervisor",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="session_selected",
            actor_id=sample_user.id,
            actor_role="admin",
            payload={"selected_session": str(sup_inst.id)},
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "makeup_choice"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="no_makeup_selected",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "cancelled_no_makeup"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "cancelled_no_makeup"
        assert instance.is_completed is True

    async def test_supervisor_sessions_next_4_weeks_from_50h_instance(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        sup_inst = await _seed_supervision_session(db_session, sample_student.id)
        await db_session.commit()

        sessions = await get_supervisor_sessions_next_4_weeks(
            db_session, sample_user.id, sample_student.id
        )
        assert len(sessions) == 1
        assert sessions[0]["value"] == str(sup_inst.id)

    async def test_supervisor_session_cancellation_makeup_flow_paid(
        self, db_session: AsyncSession, sample_student, sample_student_user
    ):
        """مسیر جبرانی با پرداخت قبلی: makeup_proposed → makeup_confirmed → makeup_session_completed."""
        await _load_cancel_processes(db_session)
        sup_inst = await _seed_supervision_session(db_session, sample_student.id, paid=True)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervisor_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="supervisor",
        )
        await db_session.commit()

        sid = str(sup_inst.id)
        makeup_date = (date.today() + timedelta(days=14)).isoformat()

        for trigger, role, payload in (
            ("session_selected", "admin", {"selected_session": sid}),
            (
                "makeup_date_entered",
                "admin",
                {
                    "selected_session": sid,
                    "makeup_option": "wants_makeup",
                    "proposed_date": makeup_date,
                    "proposed_time": "11:30",
                },
            ),
            (
                "student_confirmed",
                "student",
                {"student_response": "accept", "supervision_session_paid": True},
            ),
            ("session_held", "supervisor", {}),
        ):
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_student_user.id,
                actor_role=role,
                payload=payload,
            )
            await db_session.commit()
            assert result.success is True, result.error

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "makeup_session_completed"
        assert instance.is_completed is True

    async def test_supervisor_session_cancellation_makeup_unpaid_then_payment(
        self, db_session: AsyncSession, sample_student, sample_student_user
    ):
        """مسیر جبرانی بدون پرداخت: payment_pending → payment_completed → makeup_confirmed."""
        await _load_cancel_processes(db_session)
        sup_inst = await _seed_supervision_session(db_session, sample_student.id, paid=False)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervisor_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="supervisor",
        )
        await db_session.commit()

        sid = str(sup_inst.id)
        makeup_date = (date.today() + timedelta(days=10)).isoformat()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="session_selected",
            actor_id=sample_student_user.id,
            actor_role="admin",
            payload={"selected_session": sid},
        )
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="makeup_date_entered",
            actor_id=sample_student_user.id,
            actor_role="admin",
            payload={
                "selected_session": sid,
                "makeup_option": "wants_makeup",
                "proposed_date": makeup_date,
                "proposed_time": "09:00",
            },
        )
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_confirmed",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={"student_response": "accept", "supervision_session_paid": False},
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "payment_pending"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_completed",
            actor_id=sample_student_user.id,
            actor_role="system",
            payload={},
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "makeup_confirmed"

    async def test_build_supervisor_cancellation_context(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        sup_inst = await _seed_supervision_session(db_session, sample_student.id)
        await _load_cancel_processes(db_session)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervisor_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="supervisor",
        )
        instance.context_data = {**(instance.context_data or {}), "selected_session": str(sup_inst.id)}
        await db_session.flush()

        ctx = await build_supervisor_cancellation_context(db_session, instance)
        assert len(ctx.get("supervisor_sessions_next_4_weeks") or []) >= 1
        assert ctx.get("selected_session_date")

    async def test_student_counter_proposal_flow(
        self, db_session: AsyncSession, sample_student, sample_student_user
    ):
        """دانشجو پیشنهاد جایگزین می‌دهد → سوپروایزر زمان جدید ثبت می‌کند."""
        await _load_cancel_processes(db_session)
        sup_inst = await _seed_supervision_session(db_session, sample_student.id, paid=True)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervisor_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="supervisor",
        )
        await db_session.commit()

        sid = str(sup_inst.id)
        d1 = (date.today() + timedelta(days=12)).isoformat()
        d2 = (date.today() + timedelta(days=16)).isoformat()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="session_selected",
            actor_id=sample_student_user.id,
            actor_role="admin",
            payload={"selected_session": sid},
        )
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="makeup_date_entered",
            actor_id=sample_student_user.id,
            actor_role="admin",
            payload={
                "makeup_option": "wants_makeup",
                "proposed_date": d1,
                "proposed_time": "14:00",
            },
        )
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_counter_proposed",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={
                "student_response": "counter_propose",
                "counter_proposal_text": "پیشنهاد: جمعه ساعت ۱۵",
            },
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "supervisor_review_counter"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="supervisor_entered_new_time",
            actor_id=sample_student_user.id,
            actor_role="supervisor",
            payload={"proposed_date": d2, "proposed_time": "15:00"},
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "makeup_proposed"
