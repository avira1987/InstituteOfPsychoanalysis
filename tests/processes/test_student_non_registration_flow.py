"""Test student_non_registration flow (process 42)."""

import pytest
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.meta.student_step_forms import apply_register_to_context


@pytest.mark.asyncio
class TestStudentNonRegistrationFlow:

    async def _load(self, db_session: AsyncSession) -> StateMachineEngine:
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "student_non_registration.json")
        await db_session.commit()
        return StateMachineEngine(db_session)

    async def test_load_and_start_list_generated(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="student_non_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={"term_code": "fall-2026-test"},
        )
        await db_session.commit()
        assert instance.process_code == "student_non_registration"
        assert instance.current_state_code == "list_generated"

    async def test_meeting_scheduled_to_meeting_held(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="student_non_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        ctx = dict(instance.context_data or {})
        ctx = apply_register_to_context(
            ctx,
            "list_generated",
            {
                "committee_meeting_at": "2026-06-15T10:00:00+00:00",
                "committee_meeting_mode": "in_person",
                "committee_meeting_location_fa": "انستیتو روانکاوی تهران",
            },
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="meeting_scheduled",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "meeting_held"

    async def test_choice_leave_after_meeting_result(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="student_non_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        ctx = dict(instance.context_data or {})
        ctx = apply_register_to_context(
            ctx,
            "list_generated",
            {
                "committee_meeting_at": "2026-06-15T10:00:00+00:00",
                "committee_meeting_mode": "online",
                "committee_meeting_link": "https://meet.example.com/room",
            },
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="meeting_scheduled",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)

        ctx = dict(instance.context_data or {})
        ctx = apply_register_to_context(
            ctx,
            "meeting_held",
            {"weeks_since_start": 2, "decision": "leave"},
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="choice_leave",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
            payload={"decision": "leave"},
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "branch_leave"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "branch_leave"
        assert instance.context_data.get("branch_leave_entered_at")

    async def test_choice_register_blocked_after_four_weeks(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        extra = dict(sample_student.extra_data or {})
        extra["term_start_date"] = (date.today() - timedelta(days=35)).isoformat()
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.flush()

        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="student_non_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        ctx = dict(instance.context_data or {})
        ctx = apply_register_to_context(ctx, "list_generated", {
            "committee_meeting_at": "2026-06-15T10:00:00+00:00",
            "committee_meeting_mode": "in_person",
            "committee_meeting_location_fa": "انستیتو",
        })
        ctx = apply_register_to_context(ctx, "meeting_held", {
            "weeks_since_start": 5,
            "decision": "register",
        })
        instance.context_data = ctx
        instance.current_state_code = "meeting_held"
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="choice_register",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
            payload={"decision": "register", "weeks_since_start": 5},
        )
        await db_session.commit()
        assert result.success is False
