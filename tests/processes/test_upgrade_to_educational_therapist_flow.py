"""Test upgrade_to_educational_therapist flow (process 71)."""

import pytest
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.process_forms import get_process_forms
from app.meta.seed import load_process, load_rules
from app.models.operational_models import Student
from app.services.attendance_service import AttendanceService


@pytest.fixture(autouse=True)
def _patch_attendance_for_et_flow(monkeypatch: pytest.MonkeyPatch):
    async def _therapy_metrics(self, student_id):
        return {"therapy_hours_2x": 10.0, "clinical_hours": 200.0, "supervision_hours": 5.0}

    async def _hours(self, student_id):
        return {"total_hours": 100}

    monkeypatch.setattr(AttendanceService, "get_therapy_completion_metrics", _therapy_metrics)
    monkeypatch.setattr(AttendanceService, "get_completed_hours", _hours)


@pytest.mark.asyncio
class TestUpgradeToEducationalTherapistFlow:

    async def test_forms_load_for_key_states(self):
        monitoring = get_process_forms("upgrade_to_educational_therapist", state_code="monitoring_review")
        assert len(monitoring) == 1
        assert monitoring[0]["code"] == "et_monitoring_decision"

        slots = get_process_forms("upgrade_to_educational_therapist", state_code="et_availability_slots")
        assert len(slots) == 1
        names = {f["name"] for f in slots[0]["fields"]}
        assert {"slot_1_day", "slot_1_time", "slot_2_day", "slot_2_time"}.issubset(names)

    async def test_starts_and_conditions_met_to_monitoring(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "upgrade_to_educational_therapist.json")
        await db_session.commit()

        extra = dict(sample_student.extra_data or {})
        extra["et_eligibility_rank_ok"] = True
        extra["et_therapy_baseline_met"] = True
        extra["supervision_monthly_sessions"] = 2
        sample_student.extra_data = extra
        sample_student.therapy_started = True
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="upgrade_to_educational_therapist",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="student",
            initial_context={"acknowledge": True},
        )
        await db_session.commit()
        assert instance.current_state_code == "student_start"

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="conditions_met",
            actor_id=sample_user.id,
            actor_role="student",
            payload={"acknowledge": True},
        )
        await db_session.commit()
        assert result.success, result.error
        assert result.to_state == "monitoring_review"

    async def test_monitoring_approved_to_interview_scheduling(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
        await load_rules(db_session)
        await load_process(db_session, processes_dir / "upgrade_to_educational_therapist.json")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="upgrade_to_educational_therapist",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={"et_eligibility_met": True},
        )
        ctx = dict(instance.context_data or {})
        ctx["et_eligibility_met"] = True
        instance.context_data = ctx
        instance.current_state_code = "monitoring_review"
        flag_modified(instance, "context_data")
        await db_session.commit()

        result = await engine.execute_transition(
            instance_id=instance.id,
            trigger_event="approved",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
            payload={"result": "approve"},
        )
        await db_session.commit()
        assert result.success, result.error
        assert result.to_state == "interview_scheduling"
