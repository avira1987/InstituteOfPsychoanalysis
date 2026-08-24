"""Slice 1 / Phase B: student cancel >12% → violation hub → committee verdict."""

from datetime import date, timedelta
from pathlib import Path
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.meta.student_step_forms import apply_register_to_context
from app.models.operational_models import ProcessInstance, TherapySession, User


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"


@pytest.mark.asyncio
class TestStudentSessionCancellationViolationChain:
    async def _load(self, db_session: AsyncSession) -> StateMachineEngine:
        await load_rules(db_session)
        await load_process(db_session, PROCESSES_DIR / "student_session_cancellation.json")
        await load_process(db_session, PROCESSES_DIR / "violation_registration.json")
        await load_process(db_session, PROCESSES_DIR / "fee_determination.json")
        await db_session.commit()
        return StateMachineEngine(db_session)

    async def test_cancel_above_12_percent_spawns_violation_and_minor_verdict(
        self,
        db_session: AsyncSession,
        sample_student,
        sample_student_user: User,
        sample_user: User,
    ):
        engine = await self._load(db_session)
        upcoming = TherapySession(
            student_id=sample_student.id,
            therapist_id=sample_user.id,
            session_date=date.today() + timedelta(days=2),
            status="scheduled",
            is_extra=False,
            payment_status="pending",
        )
        db_session.add(upcoming)
        await db_session.commit()

        parent = await engine.start_process(
            process_code="student_session_cancellation",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert parent.current_state_code == "calendar_displayed"

        selected = [str(upcoming.id)]
        select_result = await engine.execute_transition(
            instance_id=parent.id,
            trigger_event="student_selects_sessions",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={"selected_sessions": selected},
        )
        await db_session.commit()
        assert select_result.success is True, select_result.error
        parent = await engine.get_process_instance(parent.id)
        assert parent.current_state_code == "sessions_selected"

        confirm = await engine.execute_transition(
            instance_id=parent.id,
            trigger_event="student_confirms",
            actor_id=sample_student_user.id,
            actor_role="student",
            payload={"selected_sessions": selected, "violation_ack": True},
        )
        await db_session.commit()
        assert confirm.success is True, confirm.error
        parent = await engine.get_process_instance(parent.id)
        assert parent.current_state_code == "violation_and_applied"
        viol_id = (parent.context_data or {}).get("violation_registration_instance_id")
        assert viol_id
        child = await engine.get_process_instance(uuid.UUID(str(viol_id)))
        assert child.process_code == "violation_registration"
        assert child.current_state_code == "violation_reported"
        ctx = child.context_data or {}
        assert ctx.get("parent_instance_id") == str(parent.id)
        assert ctx.get("source_process_code") == "student_session_cancellation"
        assert ctx.get("source_reason") == "student_cancellation_violation"
        assert "کنسلی بیش از ۱۲٪" in str(ctx.get("description") or "")

        fee_rows = (
            await db_session.execute(
                select(ProcessInstance).where(
                    ProcessInstance.student_id == sample_student.id,
                    ProcessInstance.process_code == "fee_determination",
                )
            )
        ).scalars().all()
        assert fee_rows
        assert any(
            (row.context_data or {}).get("parent_instance_id") == str(parent.id)
            for row in fee_rows
        )

        child.context_data = apply_register_to_context(
            dict(child.context_data or {}),
            "violation_reported",
            {
                "reviewable": "yes",
                "violation_type": "educational",
                "description": ctx.get("description") or "تخلف آموزشی — کنسلی بیش از ۱۲٪",
            },
        )
        flag_modified(child, "context_data")
        await db_session.flush()

        reviewing = await engine.execute_transition(
            instance_id=child.id,
            trigger_event="committee_reviewing",
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()
        assert reviewing.success is True, reviewing.error
        child = await engine.get_process_instance(child.id)
        assert child.current_state_code == "review_status_set"

        child.context_data = apply_register_to_context(
            dict(child.context_data or {}),
            "review_status_set",
            {
                "needs_meeting": "no",
                "verdict": "notice",
                "compensatory_conditions": "مطالعه مقررات کنسلی",
            },
        )
        flag_modified(child, "context_data")
        await db_session.flush()

        verdict = await engine.execute_transition(
            instance_id=child.id,
            trigger_event="verdict_direct",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
        )
        await db_session.commit()
        assert verdict.success is True, verdict.error
        child = await engine.get_process_instance(child.id)
        assert child.current_state_code == "verdict_issued"

        await db_session.refresh(sample_student)
        log = (sample_student.extra_data or {}).get("monitoring_performance_log") or []
        assert any(e.get("kind") == "violation" for e in log)
        assert any(e.get("verdict_action") == "notice" for e in log)
