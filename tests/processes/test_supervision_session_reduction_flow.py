"""Test supervision_session_reduction (process 24) UI context and flow."""

import pytest
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance
from app.services.action_handler import validate_supervision_reduction_preflight


@pytest.mark.asyncio
class TestSupervisionSessionReductionFlow:

    async def test_supervision_session_reduction_loads_with_forms(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "supervision_session_reduction.json"
        assert process_file.exists()

        await load_rules(db_session)
        await load_process(db_session, process_file)
        await db_session.commit()

        data = process_file.read_text(encoding="utf-8")
        assert "supervision_reduction_session_selection" in data
        assert "supervision_reduction_structure" in data

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_session_reduction",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
            initial_context={"supervision_weekly_sessions": 2},
        )
        await db_session.commit()

        assert instance.process_code == "supervision_session_reduction"
        assert instance.current_state_code == "initiated"

    async def test_path_b_multi_reduction_completed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "supervision_session_reduction.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_session_reduction",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
            initial_context={"supervision_weekly_sessions": 2},
        )
        await db_session.commit()

        r1 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="process_link_clicked",
            actor_id=sample_user.id,
            actor_role="student",
            payload={"supervision_weekly_sessions": 2},
        )
        await db_session.commit()
        assert r1.success is True, getattr(r1, "error", None)
        assert r1.to_state == "session_selection"

        r2 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="sessions_selected",
            actor_id=sample_user.id,
            actor_role="student",
            payload={
                "supervision_weekly_sessions": 2,
                "selected_sessions": ["slot_1"],
                "supervision_remaining_after_reduction": 1,
            },
        )
        await db_session.commit()
        assert r2.success is True, getattr(r2, "error", None)
        assert r2.to_state == "multi_reduction_completed"

        instance = await engine.get_process_instance(instance.id)
        assert instance.is_completed is True

    async def test_status_merge_includes_supervision_sessions(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "supervision_session_reduction.json")
        await db_session.commit()

        extra = dict(sample_student.extra_data or {})
        extra["supervision_weekly_sessions"] = 2
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_session_reduction",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
            initial_context={"supervision_weekly_sessions": 2},
        )
        await db_session.commit()

        status = await engine.get_instance_status(instance.id)
        ctx = status.get("context_data") or {}
        assert "upcoming_supervision_sessions" in ctx
        assert isinstance(ctx["upcoming_supervision_sessions"], list)
        assert len(ctx["upcoming_supervision_sessions"]) >= 2
        assert "therapy_hours_2x" in ctx
        assert "supervision_threshold" in ctx

    async def test_validate_preflight_rejects_remove_all(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "supervision_session_reduction.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="supervision_session_reduction",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
            initial_context={"supervision_weekly_sessions": 2},
        )
        await db_session.commit()

        inst = (
            await db_session.execute(select(ProcessInstance).where(ProcessInstance.id == instance.id))
        ).scalars().first()

        err = await validate_supervision_reduction_preflight(
            db_session,
            inst,
            {"selected_sessions": ["slot_1", "slot_2"]},
            sample_student,
        )
        assert err is not None
        assert "حداقل یک جلسه" in err
