"""Test live_supervision_course_completion flow (process 67 — full SOP)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules


@pytest.mark.asyncio
class TestLiveSupervisionCourseCompletionFlow:

    async def test_live_supervision_course_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "live_supervision_course_completion.json"
        assert process_file.exists()

        await load_rules(db_session)
        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="live_supervision_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
            initial_context={"course_code": "live_supervision_demo"},
        )
        await db_session.commit()

        assert instance.process_code == "live_supervision_course_completion"
        assert instance.current_state_code == "sessions_in_progress"
        assert instance.is_completed is False

    async def test_mirror_write_flow(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "live_supervision_course_completion.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="live_supervision_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
            initial_context={"course_code": "ls_demo"},
        )
        await db_session.commit()

        r1 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="mirror_attendance_recorded",
            actor_id=sample_user.id,
            actor_role="system",
            payload={"mirror_session_index": 1},
        )
        await db_session.commit()
        assert r1.success is True, r1.error
        assert r1.to_state == "mirror_implementation_pending"

        r2 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="mirror_write_submitted",
            actor_id=sample_user.id,
            actor_role="student",
            payload={"mirror_implementation_text": "پیاده‌سازی تست"},
        )
        await db_session.commit()
        assert r2.success is True, r2.error
        assert r2.to_state == "sessions_in_progress"

    async def test_final_eval_to_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "live_supervision_course_completion.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="live_supervision_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
            initial_context={"course_code": "ls_demo"},
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="eighteenth_attendance_recorded",
            actor_id=sample_user.id,
            actor_role="system",
            payload={
                "live_supervision_normal_count": 15,
                "live_supervision_mirror_count": 3,
            },
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "final_eval_pending"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="final_eval_submitted",
            actor_id=sample_user.id,
            actor_role="instructor",
            payload={
                "q7_has_positive": "no",
                "q8_has_negative": "no",
            },
        )
        await db_session.commit()
        assert result.success is True, result.error
        assert result.to_state == "completed"
        instance = await engine.get_process_instance(instance.id)
        assert instance.is_completed is True
