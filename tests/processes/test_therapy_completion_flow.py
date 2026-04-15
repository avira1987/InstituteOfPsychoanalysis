"""Test therapy_completion flow (BUILD_TODO hande h - item 2)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules


@pytest.mark.asyncio
class TestTherapyCompletionFlow:

    async def test_therapy_completion_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "therapy_completion.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert instance.process_code == "therapy_completion"
        assert instance.current_state_code == "initiated"
        assert instance.is_completed is False

    async def test_therapy_completion_flow_to_therapy_completed(
        self, db_session: AsyncSession, sample_student, sample_user, monkeypatch: pytest.MonkeyPatch
    ):
        async def fake_resolved(self, instance):
            return {
                "therapy_hours_2x": 250.0,
                "clinical_hours": 750.0,
                "supervision_hours": 150.0,
                "therapy_threshold": 250.0,
                "clinical_threshold": 750.0,
                "supervision_threshold": 150.0,
                "therapy_hours": 250.0,
                "therapy_completion_preview_fa": "وضعیت ساعات (تست): همه حدنصاب‌ها برآورده است.",
            }

        monkeypatch.setattr(StateMachineEngine, "_therapy_completion_resolved_fields", fake_resolved)

        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "therapy_completion.json")
        await db_session.commit()
        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="therapy_completion",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="process_link_clicked",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True, getattr(result, "error", None)
        assert result.to_state == "therapy_completed"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "therapy_completed"
        assert instance.is_completed is True
