"""Test live session prep flows (processes 66 and 68)."""

import pytest
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.meta.student_step_forms import apply_register_to_context


REFERRAL_FORM = {
    "patient_first_name": "علی",
    "patient_last_name": "رضایی",
    "patient_phone": "09123334444",
    "referral_notes": "بیمار متقاضی پشت آینه",
}

SCHEDULE_FORM = {
    "instructor_id": "00000000-0000-4000-8000-000000000001",
    "therapist_id": "00000000-0000-4000-8000-000000000002",
    "session_date": "2026-07-15",
    "session_time": "14:30",
}


@pytest.mark.asyncio
class TestLiveSessionPrepFlow:
    @pytest.mark.parametrize(
        "process_code",
        [
            "live_supervision_session_prep",
            "live_therapy_observation_session_prep",
        ],
    )
    async def test_happy_path_to_session_scheduled(
        self, db_session: AsyncSession, sample_student, sample_user, process_code: str
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / f"{process_code}.json")
        await load_rules(db_session)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code=process_code,
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()
        assert instance.current_state_code == "patient_referral"

        ctx = apply_register_to_context(
            dict(instance.context_data or {}),
            "patient_referral",
            REFERRAL_FORM,
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        step1 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="referral_submitted",
            actor_id=sample_user.id,
            actor_role="admission_officer",
            payload=dict(REFERRAL_FORM),
        )
        await db_session.commit()
        assert step1.success is True
        assert step1.to_state == "coordination_pending"

        ctx2 = apply_register_to_context(
            dict(instance.context_data or {}),
            "coordination_pending",
            SCHEDULE_FORM,
        )
        instance.context_data = ctx2
        flag_modified(instance, "context_data")
        await db_session.flush()

        step2 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="time_registered",
            actor_id=sample_user.id,
            actor_role="therapy_education_coordinator",
            payload={**SCHEDULE_FORM, "session_time_registered": True},
        )
        await db_session.commit()
        assert step2.success is True
        assert step2.to_state == "session_scheduled"

    @pytest.mark.parametrize(
        "process_code",
        [
            "live_supervision_session_prep",
            "live_therapy_observation_session_prep",
        ],
    )
    async def test_coordination_closed_when_no_time(
        self, db_session: AsyncSession, sample_student, sample_user, process_code: str
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_process(db_session, processes_dir / f"{process_code}.json")
        await load_rules(db_session)
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code=process_code,
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
        )
        await db_session.commit()

        ctx = apply_register_to_context(
            dict(instance.context_data or {}),
            "patient_referral",
            REFERRAL_FORM,
        )
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.flush()

        await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="referral_submitted",
            actor_id=sample_user.id,
            actor_role="admission_officer",
            payload=dict(REFERRAL_FORM),
        )
        await db_session.commit()

        step2 = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="no_time_agreed",
            actor_id=sample_user.id,
            actor_role="therapy_education_coordinator",
            payload={"session_time_registered": False},
        )
        await db_session.commit()
        assert step2.success is True
        assert step2.to_state == "coordination_closed"
