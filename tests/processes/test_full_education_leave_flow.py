"""Tests for process 59 — full_education_leave."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.services.full_education_leave_service import build_leave_context


@pytest.mark.asyncio
class TestFullEducationLeaveService:

    async def test_build_leave_context_non_intern(self, db_session: AsyncSession, sample_student):
        ctx = await build_leave_context(db_session, sample_student.id, {"leave_terms": 1})
        assert ctx["is_intern"] is False
        assert ctx["leave_terms_display"] == "یک ترم"
        assert "has_active_therapist" in ctx


@pytest.mark.asyncio
class TestFullEducationLeaveFlow:

    async def test_full_education_leave_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user,
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "full_education_leave.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="full_education_leave",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "full_education_leave"
        assert instance.current_state_code == "leave_request"
        assert instance.is_completed is False
        assert instance.context_data.get("is_intern_display_fa") in ("انترن", "غیر انترن")

    async def test_full_education_leave_submit_goes_to_committee(
        self, db_session: AsyncSession, sample_student, sample_student_user,
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "full_education_leave.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="full_education_leave",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={"leave_terms": 2, "request_reason": "test"},
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "committee_review"

    async def test_full_education_leave_reject_flow(
        self, db_session: AsyncSession, sample_student, sample_student_user, sample_user,
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "full_education_leave.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="full_education_leave",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={"leave_terms": 1},
        )
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="committee_set_meeting",
            actor_id=sample_user.id,
            actor_role="admin",
            payload={
                "committee_meeting_at": "2026-09-15T10:30:00+00:00",
                "committee_meeting_mode": "in_person",
                "committee_meeting_location_fa": "اتاق کمیته",
            },
        )
        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="meeting_held",
            actor_id=sample_user.id,
            actor_role="admin",
            payload={},
        )
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="committee_rejected",
            actor_id=sample_user.id,
            actor_role="admin",
            payload={"rejection_reason_fa": "رد آزمایشی"},
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "leave_rejected"
