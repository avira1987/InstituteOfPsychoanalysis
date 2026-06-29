"""Test specialized_commission_review flow (BUILD_TODO hande h - item 10)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestSpecializedCommissionReviewFlow:

    async def test_specialized_commission_review_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "specialized_commission_review.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="specialized_commission_review",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert instance.process_code == "specialized_commission_review"
        assert instance.current_state_code == "commission_review"
        assert instance.is_completed is False

    async def test_specialized_commission_review_flow_to_referred_to_committees(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "specialized_commission_review.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="specialized_commission_review",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="commission_rejected",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "referred_to_committees"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "referred_to_committees"
        assert instance.is_completed is True

    async def test_specialized_commission_review_flow_to_awaiting_restart(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        from app.meta.student_step_forms import CTX_SUBMITTED

        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "specialized_commission_review.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="specialized_commission_review",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={
                "termination_reason_code": 3,
                "termination_note": "یادداشت تست",
            },
        )
        await db_session.commit()
        ctx = dict(instance.context_data or {})
        ctx[CTX_SUBMITTED] = {"commission_review": True}
        ctx["commission_meeting_notes_fa"] = "جلسه برگزار شد"
        ctx["commission_opinion_fa"] = "صلاحیت تأیید شد"
        instance.context_data = ctx
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="commission_approved",
            actor_id=sample_user.id,
            actor_role="specialized_commission",
            payload={
                "commission_meeting_notes_fa": "جلسه برگزار شد",
                "commission_opinion_fa": "صلاحیت تأیید شد",
                "commission_result": "eligibility_confirmed",
            },
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "awaiting_student_restart"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "awaiting_student_restart"
        assert instance.is_completed is False
        assert instance.context_data.get("awaiting_restart_entered_at")
