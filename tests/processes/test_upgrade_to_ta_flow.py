"""Test upgrade_to_ta as جریان بزرگ (BUILD_TODO item ۱۷ — ه: ارتقا به کمک‌مدرس)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestUpgradeToTaFlow:

    async def test_upgrade_to_ta_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ارتقا به کمک‌مدرس لود و استارت می‌شود؛ state اول student_click است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "upgrade_to_ta.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="upgrade_to_ta",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "upgrade_to_ta"
        assert instance.current_state_code == "student_click"
        assert instance.is_completed is False

    async def test_status_includes_ta_eligibility_context(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """وضعیت نمونه باید فیلدهای احراز شرایط کمک‌مدرس را برگرداند."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "upgrade_to_ta.json")
        sample_student.is_intern = True
        extra = dict(sample_student.extra_data or {})
        extra["ta_eligibility_gpa_ok"] = True
        extra["ta_eligibility_therapy_ok"] = True
        extra["comprehensive_term2_courses_passed"] = True
        sample_student.extra_data = extra
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="upgrade_to_ta",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        status = await engine.get_instance_status(instance.id)
        ctx = status.get("context_data") or {}
        assert "ta_eligibility_summary_fa" in ctx
        assert "ta_conditions_preview" in ctx
        assert ctx.get("ta_eligibility_met") is True

    async def test_upgrade_to_ta_full_flow_to_ta_registered(
        self, db_session: AsyncSession, sample_student, sample_user, sample_student_user
    ):
        """جریان کامل: student_click → supervision_review → ... → ta_registered (با admin و student)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "upgrade_to_ta.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="upgrade_to_ta",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        sample_student.is_intern = True
        extra = dict(sample_student.extra_data or {})
        extra.update({
            "comprehensive_term2_courses_passed": True,
            "ta_eligibility_gpa_ok": True,
            "ta_eligibility_therapy_ok": True,
        })
        sample_student.extra_data = extra
        await db_session.commit()

        # conditions_met → supervision_review
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="conditions_met",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "supervision_review"

        # approved → interview_scheduling
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="approved",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "interview_scheduling"

        # interview_scheduled → interview_held
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="interview_scheduled",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "interview_held"

        # approved → track_selection
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="approved",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "track_selection"

        # tracks_registered → commitment_signature
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="tracks_registered",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "commitment_signature"

        # commitment_signed → ta_registered (required_role: student)
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="commitment_signed",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "ta_registered"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "ta_registered"
        assert instance.is_completed is True
