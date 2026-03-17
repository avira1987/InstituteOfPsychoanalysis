"""Test fall_semester_preparation as first جریان بزرگ (BUILD_TODO section 5 — ه)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestFallSemesterPreparationFlow:

    async def test_fall_semester_preparation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند آماده‌سازی ترم پاییز لود و استارت می‌شود؛ state اول calendar_entry است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "fall_semester_preparation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="course_committee_executive",
        )
        await db_session.commit()

        assert instance.process_code == "fall_semester_preparation"
        assert instance.current_state_code == "calendar_entry"
        assert instance.is_completed is False

    async def test_fall_semester_preparation_has_forward_transition_from_calendar(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """از state calendar_entry نقش course_committee_executive می‌تواند با calendar_submitted به tuition_entry برود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="course_committee_executive",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            "course_committee_executive",
        )
        trigger_events = [t["trigger_event"] for t in transitions]
        assert "calendar_submitted" in trigger_events

    async def test_fall_semester_preparation_transition_to_tuition_entry(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """اجرای transition calendar_submitted باعث رفتن به tuition_entry می‌شود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="course_committee_executive",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="calendar_submitted",
            actor_id=sample_user.id,
            actor_role="course_committee_executive",
        )
        await db_session.commit()

        assert result.success is True
        assert result.from_state == "calendar_entry"
        assert result.to_state == "tuition_entry"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "tuition_entry"
