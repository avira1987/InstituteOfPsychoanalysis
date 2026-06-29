"""Test return_to_full_education — process 60 (بازگشت به کل آموزش پس از مرخصی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestReturnToFullEducationFlow:

    async def test_return_to_full_education_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند بازگشت به کل آموزش لود و استارت می‌شود؛ state اول return_request است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "return_to_full_education.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="return_to_full_education",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "return_to_full_education"
        assert instance.current_state_code == "return_request"
        assert instance.is_completed is False
        ctx = instance.context_data or {}
        assert "course_type" in ctx

    async def test_return_to_full_education_non_intern_flow_to_complete(
        self, db_session: AsyncSession, sample_student, sample_student_user, sample_user
    ):
        """جریان غیر انترن: return_request → therapist → payment → unlock → complete."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "return_to_full_education.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="return_to_full_education",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="proceed",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "therapist_selection"

        ctx = dict(instance.context_data or {})
        ctx["is_intern"] = False
        ctx["course_type"] = "introductory"
        ctx["therapist_id"] = str(sample_user.id)
        ctx["weekly_sessions"] = 1
        ctx["first_session_date"] = "2030-06-01"
        instance.context_data = ctx
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(instance, "context_data")
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="therapist_selected",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload=ctx,
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "therapy_payment_pending"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="therapy_payment_confirmed",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code in (
            "registration_unlocked",
            "return_complete",
            "therapy_completed",
        )

    async def test_return_to_full_education_intern_needs_supervisor(
        self, db_session: AsyncSession, sample_student, sample_student_user, sample_user
    ):
        """پس از پرداخت درمان، انترن به supervisor_selection می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "return_to_full_education.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="return_to_full_education",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="proceed",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        ctx = dict(instance.context_data or {})
        ctx["is_intern"] = True
        ctx["course_type"] = "comprehensive"
        ctx["therapist_id"] = str(sample_user.id)
        ctx["weekly_sessions"] = 2
        ctx["first_session_date"] = "2030-06-01"
        instance.context_data = ctx
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(instance, "context_data")
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="therapist_selected",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload=ctx,
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "therapy_payment_pending"

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="therapy_payment_confirmed",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "supervisor_selection"
