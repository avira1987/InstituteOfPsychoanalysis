"""Test violation_registration process (BUILD_TODO section 1)."""

import pytest
import pytest_asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process


@pytest.mark.asyncio
class TestViolationRegistrationProcess:

    async def test_violation_registration_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """violation_registration process can be loaded from JSON and started for a student."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "violation_registration.json"
        assert process_file.exists(), "violation_registration.json must exist"

        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="violation_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()

        assert instance.process_code == "violation_registration"
        assert instance.current_state_code == "violation_reported"
        assert instance.is_completed is False

    async def test_violation_registration_has_available_transitions(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        """After start, monitoring_committee_officer has transitions from violation_reported."""
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / "violation_registration.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="violation_registration",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="monitoring_committee_officer",
        )
        await db_session.commit()

        transitions = await engine.get_available_transitions(
            instance.id,
            "monitoring_committee_officer",
        )
        assert len(transitions) >= 1
        trigger_events = [t["trigger_event"] for t in transitions]
        assert "committee_reviewing" in trigger_events or "recorded_and_closed" in trigger_events
