"""Test intern_hours_increase flow (BUILD_TODO ه — بسته انترنشیپ)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestInternHoursIncreaseFlow:

    async def test_intern_hours_increase_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند intern_hours_increase لود و استارت می‌شود؛ state اول deadline_reached است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "intern_hours_increase.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="intern_hours_increase",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "intern_hours_increase"
        assert instance.current_state_code == "deadline_reached"
        assert instance.is_completed is False

    async def test_intern_hours_increase_flow_to_hours_increased(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی تایید: deadline_reached → supervision_review → approved_time_coordination → hours_increased."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "intern_hours_increase.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="intern_hours_increase",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        # deadline_reached -> supervision_review
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="alert_to_supervision",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "supervision_review"

        # supervision_review -> approved_time_coordination
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="approved",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "approved_time_coordination"

        # approved_time_coordination -> hours_increased
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="times_registered",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "hours_increased"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "hours_increased"
        assert instance.is_completed is True

