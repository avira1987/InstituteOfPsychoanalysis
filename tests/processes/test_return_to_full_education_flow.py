"""Test return_to_full_education as جریان بزرگ (BUILD_TODO item ۲۶ — ه بخش ۲۳: بازگشت به کل آموزش پس از مرخصی)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestReturnToFullEducationFlow:

    async def test_return_to_full_education_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند بازگشت به کل آموزش لود و استارت می‌شود؛ state اول return_request است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "return_to_full_education.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="return_to_full_education",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "return_to_full_education"
        assert instance.current_state_code == "return_request"
        assert instance.is_completed is False

    async def test_return_to_full_education_flow_to_return_approved(
        self, db_session: AsyncSession, sample_student, sample_user, sample_student_user
    ):
        """جریان: return_request → clinical_roles_selection → return_approved."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "return_to_full_education.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="return_to_full_education",
            student_id=sample_student.id,
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="request_submitted",
            actor_id=sample_student_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "clinical_roles_selection"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="roles_assigned",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "return_approved"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "return_approved"
        assert instance.is_completed is True
