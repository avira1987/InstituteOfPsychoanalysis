"""Test internship_readiness_consultation flow (BUILD_TODO ه — بسته انترنشیپ)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestInternshipReadinessConsultationFlow:

    async def test_internship_readiness_consultation_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """فرایند internship_readiness_consultation لود و استارت می‌شود؛ state اول auto_trigger است."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "internship_readiness_consultation.json"
        assert process_file.exists()

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="internship_readiness_consultation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        assert instance.process_code == "internship_readiness_consultation"
        assert instance.current_state_code == "auto_trigger"
        assert instance.is_completed is False

    async def test_internship_readiness_consultation_full_flow_to_internship_started(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """سناریوی خوش‌بینانه تا آغاز انترنی: auto_trigger → ... → internship_started."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "internship_readiness_consultation.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="internship_readiness_consultation",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        # auto_trigger -> student_request
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="student_registered_request",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "student_request"

        # student_request -> supervision_committee_review
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="request_submitted",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "supervision_committee_review"

        # supervision_committee_review -> interview_scheduling
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="supervision_approved",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "interview_scheduling"

        # interview_scheduling -> interview_held
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="interview_scheduled",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "interview_held"

        # interview_held -> interview_result_unconditional
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="result_unconditional",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "interview_result_unconditional"

        # interview_result_unconditional -> contract_practice
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="proceed_to_contracts",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "contract_practice"

        # contract_practice -> contract_rules
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="practice_contract_signed",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "contract_rules"

        # contract_rules -> promissory_note
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="rules_contract_signed",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "promissory_note"

        # promissory_note -> capacity_check
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="promissory_received",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "capacity_check"

        # capacity_check -> supervisor_selection
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="patient_available",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "supervisor_selection"

        # supervisor_selection -> first_session_payment
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="supervisor_and_time_selected",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "first_session_payment"

        # first_session_payment -> internship_started
        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="payment_completed",
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert result.success is True
        assert result.to_state == "internship_started"

        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "internship_started"
        assert instance.is_completed is True

