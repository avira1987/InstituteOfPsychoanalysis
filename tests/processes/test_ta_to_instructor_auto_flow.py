"""Test ta_to_instructor_auto flow (BUILD_TODO ه — بسته TA)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process
from app.services.ta_to_instructor_auto_service import (
    evaluate_ta_to_instructor_eligibility,
    persist_ta_to_instructor_context,
    run_auto_ta_to_instructor_transition,
)


def _seed_eligible_student_extra(student) -> None:
    extra = dict(student.extra_data or {})
    extra["rank"] = "assistant_faculty"
    extra["lms"] = {
        **(extra.get("lms") or {}),
        "ta_course_passes": {"theory_psychoanalysis_1": 2},
        "ta_course_tracks": {"theory_psychoanalysis_1": "analytic_psychotherapy"},
        "track_course_sequences": {
            "analytic_psychotherapy": [
                "theory_psychoanalysis_1",
                "theory_psychoanalysis_2",
            ],
        },
    }
    student.extra_data = extra
    flag_modified(student, "extra_data")


@pytest.mark.asyncio
class TestTaToInstructorAutoFlow:

    async def test_ta_to_instructor_auto_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند ta_to_instructor_auto لود و استارت می‌شود؛ state اول end_of_term_check است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "ta_to_instructor_auto.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_instructor_auto",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "ta_to_instructor_auto"
        assert instance.current_state_code == "end_of_term_check"
        assert instance.is_completed is False

    async def test_evaluate_eligibility_fails_without_rank_and_passes(
        self, db_session: AsyncSession, sample_student, sample_student_user
    ):
        ev = evaluate_ta_to_instructor_eligibility(sample_student, sample_student_user)
        assert ev["eligible"] is False
        assert ev["rank_ok"] is False
        assert ev["passes_ok"] is False

    async def test_evaluate_eligibility_passes_with_seed_data(
        self, db_session: AsyncSession, sample_student, sample_student_user
    ):
        _seed_eligible_student_extra(sample_student)
        await db_session.commit()

        ev = evaluate_ta_to_instructor_eligibility(sample_student, sample_student_user)
        assert ev["eligible"] is True
        assert ev["rank_ok"] is True
        assert ev["passes_ok"] is True
        assert ev["source_course_code"] == "theory_psychoanalysis_1"
        assert ev["next_course_code"] == "theory_psychoanalysis_2"

    async def test_auto_transition_conditions_failed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_to_instructor_auto.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_instructor_auto",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        to_state = await run_auto_ta_to_instructor_transition(db_session, instance)
        await db_session.commit()

        assert to_state == "conditions_not_met"
        refreshed = await engine.get_process_instance(instance.id)
        assert refreshed.current_state_code == "conditions_not_met"
        assert refreshed.is_completed is True

    async def test_auto_transition_conditions_met_with_context(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریو: end_of_term_check → upgrade_applied با conditions_met و context غنی."""
        _seed_eligible_student_extra(sample_student)
        await db_session.commit()

        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_to_instructor_auto.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_instructor_auto",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        to_state = await run_auto_ta_to_instructor_transition(db_session, instance)
        await db_session.commit()

        assert to_state == "upgrade_applied"
        refreshed = await engine.get_process_instance(instance.id)
        assert refreshed.current_state_code == "upgrade_applied"
        assert refreshed.is_completed is True

        ctx = refreshed.context_data or {}
        assert ctx.get("eligible") is True
        assert ctx.get("source_course_code") == "theory_psychoanalysis_1"
        assert ctx.get("next_course_code") == "theory_psychoanalysis_2"
        assert ctx.get("upgrade_applied_at")

    async def test_ta_to_instructor_auto_flow_to_upgrade_applied(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریو: end_of_term_check → upgrade_applied با conditions_met (دستی)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "ta_to_instructor_auto.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_instructor_auto",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        await persist_ta_to_instructor_context(db_session, instance)
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="conditions_met",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "upgrade_applied"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "upgrade_applied"
        assert instance.is_completed is True
