"""Test skills_course_completion flow (BUILD_TODO ه — بسته completion/evaluation)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules


@pytest.mark.asyncio
class TestSkillsCourseCompletionFlow:

    async def _load_process(self, db_session: AsyncSession):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "skills_course_completion.json")
        await db_session.commit()
        return processes_dir

    async def test_skills_course_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند skills_course_completion لود و استارت می‌شود؛ state اول awaiting_session_17 است."""
        await self._load_process(db_session)

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="skills_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
            initial_context={"course_code": "technique_skills_1"},
        )
        await db_session.commit()

        assert instance.process_code == "skills_course_completion"
        assert instance.current_state_code == "awaiting_session_17"
        assert instance.is_completed is False

    async def test_skills_course_completion_full_path_no_ta(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی نرمال بدون TA: جلسه ۱۷ → ۱۸ → ارزیابی کیفی → قفل."""
        await self._load_process(db_session)
        engine = StateMachineEngine(db_session)
        sid = str(sample_student.id)

        instance = await engine.start_process(
            process_code="skills_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
            initial_context={
                "course_code": "technique_skills_1",
                "course_has_ta": False,
                "session_17_submitted_before_sla": True,
                "qualitative_submitted_before_sla": True,
            },
        )
        await db_session.commit()

        steps = [
            ("calendar_session_17_reached", "system", {}),
            ("session_17_submitted", "instructor", {
                "students_grades": [{
                    "student_id": sid,
                    "student_name": "تست",
                    "participation_score": 8,
                    "practical_score": 50,
                }],
            }),
            ("calendar_session_18_reached", "system", {}),
            ("session_18_submitted", "instructor", {
                "students_grades": [{
                    "student_id": sid,
                    "student_name": "تست",
                    "test_score": 18,
                    "participation_score": 8,
                    "practical_score": 50,
                    "absence_count": 0,
                }],
            }),
            ("qualitative_submitted", "instructor", {
                "q7_has_positive": "no",
                "q8_has_negative": "no",
            }),
        ]

        for trigger, role, payload in steps:
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role=role,
                payload=payload,
            )
            await db_session.commit()
            assert result.success is True, f"{trigger}: {result.error}"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "grades_locked"
        assert instance.is_completed is True

    async def test_skills_session_17_sla_breach(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """تأخیر جلسه ۱۷ → session_17_delay."""
        await self._load_process(db_session)
        engine = StateMachineEngine(db_session)

        instance = await engine.start_process(
            process_code="skills_course_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
            initial_context={
                "course_code": "technique_skills_1",
                "session_17_submitted_before_sla": False,
            },
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="calendar_session_17_reached",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="sla_breach",
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        assert result.success is True, result.error
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "session_17_delay"
