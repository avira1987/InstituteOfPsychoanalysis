"""Test comprehensive_term_end as جریان بزرگ (BUILD_TODO item ۱۳ — ه: پایان ترم جامع)."""

import pytest
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import Student


@pytest.mark.asyncio
class TestComprehensiveTermEndFlow:

    async def test_comprehensive_term_end_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند پایان ترم دوره جامع لود و استارت می‌شود؛ state اول grades_submitted است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "comprehensive_term_end.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert instance.process_code == "comprehensive_term_end"
        assert instance.current_state_code == "grades_submitted"
        assert instance.is_completed is False

    async def test_comprehensive_term_end_transition_to_transcript_generated(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از grades_submitted با trigger all_grades_entered به transcript_generated می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "comprehensive_term_end.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="all_grades_entered",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "grades_submitted"
        assert result.to_state == "transcript_generated"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "transcript_generated"

    async def test_comprehensive_term_end_transition_to_graduation_check(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از transcript_generated با trigger transcripts_ready به graduation_check می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "comprehensive_term_end.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="all_grades_entered",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="transcripts_ready",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "transcript_generated"
        assert result.to_state == "graduation_check"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "graduation_check"

    async def test_comprehensive_term_end_graduation_check_to_completed_all_courses(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از graduation_check با all_comprehensive_courses_passed و شرط all_comprehensive_subjects_passed به completed_all_courses می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "comprehensive_term_end.json")
        await db_session.commit()

        # دانشجو تمام دروس جامع را پاس کرده
        result = await db_session.execute(select(Student).where(Student.id == sample_student.id))
        student = result.scalar_one()
        student.extra_data = (student.extra_data or {}).copy()
        student.extra_data["comprehensive_courses_remaining"] = 0
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="all_grades_entered",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="transcripts_ready",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="all_comprehensive_courses_passed",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True
        assert result.to_state == "completed_all_courses"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "completed_all_courses"
        assert instance.is_completed is True

    async def test_comprehensive_term_end_graduation_check_to_registration_notification_sent(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از graduation_check با remaining_courses_exist و شرط has_remaining_comprehensive_courses به registration_notification_sent می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "comprehensive_term_end.json")
        await db_session.commit()

        result = await db_session.execute(select(Student).where(Student.id == sample_student.id))
        student = result.scalar_one()
        student.extra_data = (student.extra_data or {}).copy()
        student.extra_data["comprehensive_courses_remaining"] = 2
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="comprehensive_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="all_grades_entered",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="transcripts_ready",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="remaining_courses_exist",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True
        assert result.to_state == "registration_notification_sent"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "registration_notification_sent"
