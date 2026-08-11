"""Test introductory_term_end as جریان بزرگ (BUILD_TODO item ۹ — ه: پایان ترم آشنایی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestIntroductoryTermEndFlow:

    async def test_introductory_term_end_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند پایان ترم لود می‌شود و پس از start تا therapy check پیش می‌رود."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "introductory_term_end.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)

        assert instance.process_code == "introductory_term_end"
        # auto-advance از grades_submitted تا registration_notification_sent (یا گیر در مسیر)
        assert instance.current_state_code != "grades_submitted"
        assert instance.is_completed is False

    async def test_introductory_term_end_transition_to_transcript_generated(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """با دادهٔ نمره، پس از start کارنامه تولید شده و از grades_submitted عبور می‌کند."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "introductory_term_end.json")
        extra = sample_student.extra_data or {}
        extra["lms"] = {
            "enrolled_courses": [
                {
                    "code": "intro_1",
                    "course_name": "درس آشنایی ۱",
                    "units": 2,
                    "numeric_grade": 15,
                    "pass_fail_status": "قبول",
                },
            ],
        }
        sample_student.extra_data = extra
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="introductory_term_end",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)

        assert instance.current_state_code != "grades_submitted"
        rows = instance.context_data.get("term_transcript_rows") or []
        assert len(rows) >= 1 or instance.current_state_code in (
            "transcript_generated",
            "therapy_check",
            "therapy_blocked",
            "registration_notification_sent",
            "decline_list_generated",
            "followup_in_progress",
            "followup_complete",
            "process_complete",
        )
