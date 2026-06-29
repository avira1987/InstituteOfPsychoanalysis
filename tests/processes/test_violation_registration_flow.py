"""Test violation_registration flow (process 55)."""

import pytest
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.meta.student_step_forms import apply_register_to_context
from app.services.action_handler import ActionHandler


@pytest.mark.asyncio
class TestViolationRegistrationProcess:

    async def _load(self, db_session: AsyncSession) -> StateMachineEngine:
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "violation_registration.json")
        await db_session.commit()
        return StateMachineEngine(db_session)

    async def test_violation_registration_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="violation_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
            initial_context={
                "source_reason": "no_return_from_leave",
                "description": "عدم بازگشت از مرخصی",
            },
        )
        await db_session.commit()

        assert instance.process_code == "violation_registration"
        assert instance.current_state_code == "violation_reported"
        assert instance.is_completed is False

    async def test_reviewable_yes_to_review_status(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="violation_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()

        ctx = apply_register_to_context(
            dict(instance.context_data or {}),
            "violation_reported",
            {
                "reviewable": "yes",
                "violation_type": "educational",
                "description": "تخلف آموزشی نمونه",
            },
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="committee_reviewing",
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "review_status_set"

    async def test_verdict_direct_without_meeting(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="violation_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()

        ctx = dict(instance.context_data or {})
        ctx = apply_register_to_context(
            ctx,
            "violation_reported",
            {"reviewable": "yes", "violation_type": "disciplinary", "description": "شرح"},
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()
        await engine.execute_transition(
            instance.id, "committee_reviewing", sample_user.id, "monitoring_committee_officer"
        )
        await db_session.commit()
        instance = await engine.get_process_instance(instance.id)

        ctx = apply_register_to_context(
            dict(instance.context_data or {}),
            "review_status_set",
            {
                "needs_meeting": "no",
                "verdict": "notice",
                "compensatory_conditions": "مطالعه مقررات",
            },
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance.id, "verdict_direct", sample_user.id, "supervision_committee"
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "verdict_issued"

        await db_session.refresh(sample_student)
        log = (sample_student.extra_data or {}).get("monitoring_performance_log") or []
        assert any(e.get("kind") == "violation" for e in log)

    async def test_record_violation_performance_entry_action(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="violation_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()

        ctx = dict(instance.context_data or {})
        ctx.update({
            "violation_type": "educational",
            "description": "تست اکشن",
            "verdict": "warning_1",
        })
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        handler = ActionHandler(db_session)
        out = await handler._handle_record_violation_performance_entry(
            {"type": "record_violation_performance_entry"}, instance, ctx
        )
        await db_session.commit()
        assert out == "record_violation_performance_entry"
        await db_session.refresh(sample_student)
        log = (sample_student.extra_data or {}).get("monitoring_performance_log") or []
        assert log[-1]["verdict_action"] == "warning_1"

    async def test_minor_verdict_closes(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        engine = await self._load(db_session)
        instance = await engine.start_process(
            process_code="violation_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()

        ctx = dict(instance.context_data or {})
        ctx.update({"verdict": "warning_2", "violation_type": "educational"})
        instance.context_data = ctx
        instance.current_state_code = "verdict_issued"
        flag_modified(instance, "context_data")
        await db_session.flush()

        result = await engine.execute_transition(
            instance.id, "verdict_recorded", sample_user.id, "supervision_committee"
        )
        await db_session.commit()
        assert result.success is True
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "closed"
