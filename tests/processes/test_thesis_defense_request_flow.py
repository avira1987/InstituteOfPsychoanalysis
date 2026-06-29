"""Test thesis_defense_request flow — فرایند ۷۰."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import Student


def _seed_eligible_student(student: Student) -> None:
    extra = dict(student.extra_data or {})
    extra.update({
        "total_units": 70,
        "cumulative_gpa": 16.0,
        "clinical_hours": 800,
        "supervision_hours": 160,
        "therapy_hours_2x": 260,
        "article_writing_completion_ticked": True,
    })
    student.extra_data = extra
    flag_modified(student, "extra_data")


@pytest.mark.asyncio
class TestThesisDefenseRequestFlow:

    async def test_thesis_defense_request_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "thesis_defense_request.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await load_rules(db_session)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="thesis_defense_request",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        assert instance.process_code == "thesis_defense_request"
        assert instance.current_state_code == "eligibility_check"
        assert instance.is_completed is False

    async def test_eligibility_context_merged_on_status(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "thesis_defense_request.json")
        await load_rules(db_session)
        _seed_eligible_student(sample_student)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="thesis_defense_request",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        status = await engine.get_instance_status(instance.id)
        ctx = status["context_data"]
        assert ctx.get("units_67_b_met") is True
        assert ctx.get("all_conditions_met") is True

    async def test_psychotic_report_uploaded_to_progress_committee(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "thesis_defense_request.json")
        await load_rules(db_session)
        _seed_eligible_student(sample_student)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="thesis_defense_request",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="psychotic_report_uploaded",
            actor_id=sample_user.id,
            actor_role="student",
            payload={"psychotic_report_file": {"file_name": "report.pdf", "url": "/uploads/report.pdf"}},
        )
        await db_session.commit()
        assert result.success is True, result.error
        assert result.to_state == "progress_committee_review"

    async def test_conditions_failed_when_not_eligible(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "thesis_defense_request.json")
        await load_rules(db_session)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="thesis_defense_request",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="conditions_failed",
            actor_id=sample_user.id,
            actor_role="student",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "conditions_not_met"

    async def test_happy_path_to_defense_passed(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "thesis_defense_request.json")
        await load_rules(db_session)
        _seed_eligible_student(sample_student)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="thesis_defense_request",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        steps = [
            ("psychotic_report_uploaded", "progress_committee_review", "student"),
            ("report_approved", "supervision_committee_review", "progress_committee"),
            ("permit_issued", "thesis_upload", "supervision_committee"),
            ("thesis_uploaded", "education_committee_scheduling", "student"),
            ("schedule_registered", "first_defense_held", "education_committee"),
            ("all_grades_ab", "defense_passed", "system"),
        ]
        for trigger, expected_state, role in steps:
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role=role,
            )
            await db_session.commit()
            assert result.success is True, f"{trigger}: {result.error}"
            assert result.to_state == expected_state

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "defense_passed"
        assert instance.is_completed is True
