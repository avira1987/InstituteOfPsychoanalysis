"""Test start_therapy flow (BUILD_TODO hande h - item 1)."""

import uuid
from datetime import time
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance, TherapySession, User
from app.services.educational_therapist_slot_service import create_slot


@pytest.mark.asyncio
class TestStartTherapyFlow:

    async def test_start_therapy_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "start_therapy.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="start_therapy",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert instance.process_code == "start_therapy"
        assert instance.current_state_code == "eligibility_check"
        assert instance.is_completed is False

    async def test_therapist_selected_auto_schedules_to_payment(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """پس از انتخاب دانشجو از شیت (بدون تأیید درمانگر) به payment_pending برود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "start_therapy.json")
        await db_session.commit()

        from datetime import date as date_cls, timedelta
        from app.models.operational_models import InstituteCalendar

        sample_student.course_type = "comprehensive"
        sample_student.weekly_sessions = 2

        cal = InstituteCalendar(
            id=uuid.uuid4(),
            term_code="test-term-therapy-seed",
            is_active=True,
            term_start_date=date_cls.today(),
            term_end_date=date_cls.today() + timedelta(weeks=8),
        )
        db_session.add(cal)
        await db_session.flush()

        therapist = User(
            id=uuid.uuid4(),
            username=f"therapist_{uuid.uuid4().hex[:8]}",
            hashed_password="x",
            role="therapist",
            full_name_fa="دکتر زمان‌بندی",
            is_active=True,
        )
        db_session.add(therapist)
        await db_session.flush()

        s1 = await create_slot(
            db_session,
            therapist_user_id=therapist.id,
            day_of_week=0,  # دوشنبه
            start_local_time=time(10, 0),
            end_local_time=time(11, 0),
            course_type="comprehensive",
            week_interval=1,
        )
        s2 = await create_slot(
            db_session,
            therapist_user_id=therapist.id,
            day_of_week=2,  # چهارشنبه
            start_local_time=time(15, 0),
            end_local_time=time(16, 0),
            course_type="comprehensive",
            week_interval=1,
        )
        await db_session.flush()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="start_therapy",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        inst = (
            await db_session.execute(
                select(ProcessInstance).where(ProcessInstance.id == instance.id)
            )
        ).scalars().first()
        inst.current_state_code = "therapist_selection"
        inst.context_data = {
            "therapist_id": str(therapist.id),
            "slot_ids": [str(s1.id), str(s2.id)],
            "weekly_sessions": 2,
        }
        flag_modified(inst, "context_data")
        await db_session.flush()

        student_user = await db_session.get(User, sample_student.user_id)
        actor_id = student_user.id if student_user else sample_user.id

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="therapist_selected",
            actor_id=actor_id,
            actor_role="student",
            payload={
                "therapist_id": str(therapist.id),
                "slot_ids": [str(s1.id), str(s2.id)],
                "weekly_sessions": 2,
            },
        )
        await db_session.commit()

        assert result.success is True
        refreshed = await engine.get_process_instance(instance.id)
        assert refreshed.current_state_code == "payment_pending"
        assert refreshed.context_data.get("first_session_date")
        assert refreshed.context_data.get("start_therapy_sessions_seeded") is True
        assert refreshed.context_data.get("therapy_schedule_term_end")
        seeded_n = int(refreshed.context_data.get("therapy_sessions_seeded_count") or 0)
        assert seeded_n > 2

        sessions = (
            await db_session.execute(
                select(TherapySession).where(
                    TherapySession.student_id == sample_student.id,
                    TherapySession.notes.like(f"%start_therapy_instance:{instance.id}%"),
                )
            )
        ).scalars().all()
        assert len(sessions) == seeded_n
        assert len(sessions) > 2
        assert {ts.session_date.weekday() for ts in sessions} == {0, 2}

    async def test_start_therapy_flow_to_therapy_active(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "start_therapy.json")
        await load_process(db_session, processes_dir / "session_payment.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="start_therapy",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        inst = (await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))).scalars().first()
        inst.current_state_code = "payment_pending"
        await db_session.flush()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_confirmed",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "therapy_active"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "therapy_active"
        assert instance.is_completed is True

        pay_rows = (
            await db_session.execute(
                select(ProcessInstance).where(
                    ProcessInstance.student_id == sample_student.id,
                    ProcessInstance.process_code == "session_payment",
                )
            )
        ).scalars().all()
        assert len(pay_rows) == 1
        assert pay_rows[0].current_state_code == "payment_due"
        await db_session.refresh(sample_student)
        assert (sample_student.extra_data or {}).get("primary_instance_id") == str(pay_rows[0].id)

    async def test_payment_result_is_system_only_not_admin(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """نتیجهٔ پرداخت فقط از callback سیستم؛ ادمین نباید ببیند یا دستی بزند."""
        from app.core.engine import UnauthorizedError

        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "start_therapy.json")
        await load_process(db_session, processes_dir / "session_payment.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="start_therapy",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        inst = (
            await db_session.execute(
                select(ProcessInstance).where(ProcessInstance.id == instance.id)
            )
        ).scalars().first()
        inst.current_state_code = "payment_pending"
        await db_session.flush()

        available = await engine.get_available_transitions(instance.id, "admin")
        triggers = {t["trigger_event"] for t in available}
        assert "payment_confirmed" not in triggers
        assert "payment_failed" not in triggers

        with pytest.raises(UnauthorizedError):
            await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="payment_confirmed",
                actor_id=sample_user.id,
                actor_role="admin",
            )

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_confirmed",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "therapy_active"
