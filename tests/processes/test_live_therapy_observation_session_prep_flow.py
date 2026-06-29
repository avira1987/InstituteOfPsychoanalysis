"""Test live_therapy_observation_session_prep flow (فرایند ۶۶)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules


@pytest.mark.asyncio
class TestLiveTherapyObservationSessionPrepFlow:

    async def test_loads_and_starts(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        process_file = processes_dir / "live_therapy_observation_session_prep.json"
        assert process_file.exists()

        await load_rules(db_session)
        await load_process(db_session, process_file)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="live_therapy_observation_session_prep",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admission_officer",
        )
        await db_session.commit()

        assert instance.process_code == "live_therapy_observation_session_prep"
        assert instance.current_state_code == "patient_referral"
        assert instance.is_completed is False

    async def test_full_flow_to_session_scheduled(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "live_therapy_observation_session_prep.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="live_therapy_observation_session_prep",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admission_officer",
            initial_context={
                "patient_first_name": "علی",
                "patient_last_name": "تست",
                "patient_phone": "09120000000",
            },
        )
        await db_session.commit()

        r1 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="referral_submitted",
            actor_id=sample_user.id,
            actor_role="admission_officer",
        )
        await db_session.commit()
        assert r1.success is True, r1.error
        assert r1.to_state == "coordination_pending"

        instance = await engine.get_process_instance(instance.id)
        ctx = dict(instance.context_data or {})
        ctx.update({
            "instructor_id": str(sample_user.id),
            "therapist_id": str(sample_user.id),
            "session_date": "2026-07-01",
            "session_time": "14:30",
        })
        instance.context_data = ctx
        await db_session.commit()

        r2 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="time_registered",
            actor_id=sample_user.id,
            actor_role="therapy_education_coordinator",
            payload={"session_time_registered": True},
        )
        await db_session.commit()

        assert r2.success is True, r2.error
        assert r2.to_state == "session_scheduled"
        instance = await engine.get_process_instance(instance.id)
        assert instance.current_state_code == "session_scheduled"
        assert instance.is_completed is True
        assert instance.context_data.get("session_time_registered") is True

    async def test_coordination_closed_when_no_time(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "live_therapy_observation_session_prep.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="live_therapy_observation_session_prep",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admission_officer",
            initial_context={
                "patient_first_name": "رضا",
                "patient_last_name": "نمونه",
                "patient_phone": "09121111111",
            },
        )
        await db_session.commit()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="referral_submitted",
            actor_id=sample_user.id,
            actor_role="admission_officer",
        )
        await db_session.commit()

        r = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="no_time_agreed",
            actor_id=sample_user.id,
            actor_role="therapy_education_coordinator",
            payload={"session_time_registered": False},
        )
        await db_session.commit()

        assert r.success is True, r.error
        assert r.to_state == "coordination_closed"
        instance = await engine.get_process_instance(instance.id)
        assert instance.is_completed is True
        assert instance.context_data.get("session_time_registered") is False
