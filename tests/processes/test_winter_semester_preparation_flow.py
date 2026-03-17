"""Test winter_semester_preparation as جریان بزرگ (BUILD_TODO item ۱۶ — ه: آماده‌سازی ترم زمستان)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestWinterSemesterPreparationFlow:

    async def test_winter_semester_preparation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند آماده‌سازی ترم زمستان لود و استارت می‌شود؛ state اول license_check است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "winter_semester_preparation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="winter_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "winter_semester_preparation"
        assert instance.current_state_code == "license_check"
        assert instance.is_completed is False

    async def test_winter_semester_preparation_full_flow_to_published(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان کامل: license_check → ... → published (با نقش admin برای همه transitionها)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "winter_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="winter_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        triggers = [
            "license_reviewed",       # → course_list_review
            "course_list_reviewed",   # → course_finalization
            "courses_finalized",      # → marketing_campaign
            "marketing_started",      # → interviewer_assignment
            "interviewers_assigned",  # → interview_scheduling
            "interview_times_set",    # → published
        ]
        for trigger in triggers:
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role="admin",
            )
            await db_session.commit()
            assert result.success is True, f"transition {trigger} failed: {result.error}"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "published"
        assert instance.is_completed is True
