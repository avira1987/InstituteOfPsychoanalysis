"""Test comprehensive_term_start as جریان بزرگ (BUILD_TODO item ۱۴ — ه: آغاز ترم دوره جامع)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestComprehensiveTermStartFlow:

    async def test_comprehensive_term_start_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند آغاز ترم دوره جامع لود و استارت می‌شود؛ state اول eligibility_check است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "comprehensive_term_start.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_term_start",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "comprehensive_term_start"
        assert instance.current_state_code == "eligibility_check"
        assert instance.is_completed is False

    async def test_comprehensive_term_start_eligible_to_course_display(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از eligibility_check با trigger eligible به course_display می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "comprehensive_term_start.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_term_start",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="eligible",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "eligibility_check"
        assert result.to_state == "course_display"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "course_display"

    async def test_comprehensive_term_start_full_flow_to_registration_complete(
        self, db_session: AsyncSession, sample_student, sample_user, sample_student_user
    ):
        """جریان کامل: eligibility_check → course_display → payment_choice → payment_processing → registration_complete."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "comprehensive_term_start.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_term_start",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="eligible",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="courses_seen",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_initiated",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_confirmed",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True
        assert result.to_state == "registration_complete"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "registration_complete"
        assert instance.is_completed is True
