"""Test class_session_cancellation as جریان بزرگ (BUILD_TODO item ۲۴ — ه بخش ۲۱: کنسل جلسات کلاس درسی)."""

from datetime import date

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.services.class_session_cancellation_service import (
    compute_makeup_datetime,
    session_key,
)
from app.utils.date_utils import default_term_start


@pytest.mark.asyncio
class TestClassSessionCancellationFlow:

    async def test_class_session_cancellation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند کنسل جلسات کلاس درسی لود و استارت می‌شود؛ state اول cancellation_request است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "class_session_cancellation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="class_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
        )
        await db_session.commit()

        assert instance.process_code == "class_session_cancellation"
        assert instance.current_state_code == "cancellation_request"
        assert instance.is_completed is False

    async def test_class_session_cancellation_flow_to_makeup_scheduled(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """جریان: cancellation_request → makeup_scheduled با trigger cancellation_confirmed."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "class_session_cancellation.json")
        await db_session.commit()

        course_code = "theory_1"
        session_date = "2025-10-15"
        extra = dict(sample_student.extra_data or {})
        extra["lms"] = {
            "enrolled_courses": [course_code],
            "course_sessions": [
                {
                    "course_id": course_code,
                    "session_index": 1,
                    "session_date": session_date,
                    "session_time": "10:00",
                }
            ],
        }
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        term_start = default_term_start(date(2025, 10, 15))
        makeup_d, makeup_t, _ = compute_makeup_datetime(term_start, 1, "10:00")
        sess_key = session_key(course_code, 1, session_date)

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="class_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="instructor",
            initial_context={
                "lesson_id": course_code,
                "session_to_cancel": sess_key,
                "makeup_date": makeup_d.isoformat(),
                "makeup_time": makeup_t,
            },
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="cancellation_confirmed",
            actor_id=sample_user.id,
            actor_role="admin",
            payload={
                "lesson_id": course_code,
                "session_to_cancel": sess_key,
                "makeup_date": makeup_d.isoformat(),
                "makeup_time": makeup_t,
            },
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "makeup_scheduled"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "makeup_scheduled"
        assert instance.is_completed is True

        ctx = instance.context_data or {}
        assert ctx.get("cancellation_applied_at")
        assert ctx.get("makeup_session", {}).get("session_date") == makeup_d.isoformat()

        await db_session.refresh(sample_student)
        lms = (sample_student.extra_data or {}).get("lms") or {}
        sessions = lms.get("course_sessions") or []
        cancelled = [s for s in sessions if s.get("cancelled") is True]
        makeup_rows = [s for s in sessions if s.get("is_makeup") is True]
        assert len(cancelled) >= 1
        assert len(makeup_rows) >= 1
