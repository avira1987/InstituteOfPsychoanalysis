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

    async def test_deputy_education_can_advance_calendar_step(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """نقش پنل deputy_education باید بتواند مرحلهٔ course_committee_executive را جلو ببرد (RBAC فرایند ۲۹)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        # نقش پنل «معاون آموزش» به نقش متادیتای course_committee_executive نگاشت می‌شود.
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="calendar_submitted",
            actor_id=sample_user.id,
            actor_role="deputy_education",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "tuition_entry"

    async def test_fall_semester_preparation_full_flow_to_published(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان کامل: calendar_entry → ... → published (با نقش admin برای همه transitionها)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "fall_semester_preparation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="fall_semester_preparation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        triggers = [
            "calendar_submitted",
            "tuition_submitted",
            "license_reviewed",
            "course_list_submitted",
            "courses_finalized",
            "marketing_started",
            "interviewers_assigned",
            "interview_times_set",
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
