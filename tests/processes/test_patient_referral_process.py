"""Test patient_referral process (BUILD_TODO section 2)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestPatientReferralProcess:

    async def test_patient_referral_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """patient_referral process can be loaded from JSON and started for a student (e.g. intern)."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "patient_referral.json"
        assert process_file.exists(), "patient_referral.json must exist"

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="patient_referral",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
            initial_context={"reason": "therapy_interruption_long"},
        )
        await db_session.commit()

        assert instance.process_code == "patient_referral"
        assert instance.current_state_code == "referral_triggered"
        assert instance.is_completed is False
        assert (instance.context_data or {}).get("reason") == "therapy_interruption_long"

    async def test_patient_referral_has_available_transitions(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """After start, monitoring_committee_officer has transition from referral_triggered."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "patient_referral.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="patient_referral",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="system",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            "monitoring_committee_officer",
        )
        assert len(transitions) >= 1
        trigger_events = [t["trigger_event"] for t in transitions]
        assert "list_submitted" in trigger_events
