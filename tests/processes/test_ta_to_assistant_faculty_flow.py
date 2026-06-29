"""Test ta_to_assistant_faculty flow (process 49)."""

import pytest
import uuid
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.process_forms import get_process_forms
from app.meta.seed import load_process, load_rules
from app.models.operational_models import ProcessInstance, Student
from app.services.ta_to_assistant_faculty_service import (
    SYSTEM_ACTOR_ID,
    propagate_on_start,
    scan_ta_eligible_for_upgrade,
)


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
COURSE_CODE = "intro_psycho_1"


def _seed_ta_passes(extra: dict, *, pass_count: int = 2) -> dict:
    lms = dict(extra.get("lms") or {})
    lms["ta_course_completions"] = {
        COURSE_CODE: {"pass_count": pass_count, "last_term": "1404-1"},
    }
    lms["end_of_term_ta_evaluation_done"] = True
    lms["ta_evaluation_term"] = "1404-1"
    extra["lms"] = lms
    extra["rank"] = "teaching_assistant"
    return extra


@pytest.mark.asyncio
class TestTaToAssistantFacultyFlow:

    async def _load_process(self, db_session: AsyncSession) -> None:
        await load_rules(db_session)
        await load_process(db_session, PROCESSES_DIR / "ta_to_assistant_faculty.json")
        await db_session.commit()

    async def test_forms_load_for_supervision_review(self):
        forms = get_process_forms("ta_to_assistant_faculty", state_code="supervision_review")
        assert len(forms) == 1
        assert forms[0]["code"] == "ta_to_assistant_review"
        names = {f["name"] for f in forms[0]["fields"]}
        assert "result" in names

    async def test_start_auto_advances_to_supervision_review(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        await self._load_process(db_session)
        extra = _seed_ta_passes(dict(sample_student.extra_data or {}))
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_assistant_faculty",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={"course_code": COURSE_CODE},
        )
        await db_session.commit()
        refreshed = await db_session.get(ProcessInstance, instance.id)
        assert refreshed.current_state_code == "supervision_review"
        ctx = refreshed.context_data or {}
        assert ctx.get("ta_pass_count") >= 2
        assert ctx.get("course_code") == COURSE_CODE

    async def test_already_assistant_short_circuit(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        await self._load_process(db_session)
        extra = _seed_ta_passes(dict(sample_student.extra_data or {}))
        extra["rank"] = "assistant_faculty"
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_assistant_faculty",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={"course_code": COURSE_CODE},
        )
        await db_session.commit()
        refreshed = await db_session.get(ProcessInstance, instance.id)
        assert refreshed.current_state_code == "already_assistant"

    async def test_supervision_approved_applies_upgrade(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        await self._load_process(db_session)
        extra = _seed_ta_passes(dict(sample_student.extra_data or {}))
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_assistant_faculty",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={"course_code": COURSE_CODE},
        )
        await db_session.commit()
        refreshed = await db_session.get(ProcessInstance, instance.id)
        assert refreshed.current_state_code == "supervision_review"

        result = await engine.execute_transition(
            instance_id=refreshed.id,
            trigger_event="approved",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
            payload={"result": "approve"},
        )
        await db_session.commit()
        assert result.success, result.error
        assert result.to_state == "upgrade_applied"

        st = await db_session.get(Student, sample_student.id)
        rank = (st.extra_data or {}).get("rank")
        assert rank == "assistant_faculty"

    async def test_supervision_rejected_sets_manual_retry_flag(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        await self._load_process(db_session)
        extra = _seed_ta_passes(dict(sample_student.extra_data or {}))
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_assistant_faculty",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={"course_code": COURSE_CODE},
        )
        await db_session.commit()
        refreshed = await db_session.get(ProcessInstance, instance.id)

        result = await engine.execute_transition(
            instance_id=refreshed.id,
            trigger_event="rejected",
            actor_id=sample_user.id,
            actor_role="supervision_committee",
            payload={"result": "reject"},
        )
        await db_session.commit()
        assert result.success, result.error
        assert result.to_state == "supervision_rejected"

        st = await db_session.get(Student, sample_student.id)
        rejected = (st.extra_data or {}).get("ta_upgrade_rejected_for_course") or {}
        assert rejected.get(COURSE_CODE) is True

    async def test_manual_retry_after_rejection(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        await self._load_process(db_session)
        extra = _seed_ta_passes(dict(sample_student.extra_data or {}))
        extra["ta_upgrade_rejected_for_course"] = {COURSE_CODE: True}
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_assistant_faculty",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={
                "course_code": COURSE_CODE,
                "manual_retry": True,
            },
        )
        await db_session.commit()
        refreshed = await db_session.get(ProcessInstance, instance.id)
        assert refreshed.current_state_code == "supervision_review"

    async def test_scan_finds_eligible_student(
        self, db_session: AsyncSession, sample_student
    ):
        extra = _seed_ta_passes(dict(sample_student.extra_data or {}))
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        hits = await scan_ta_eligible_for_upgrade(db_session)
        ids = {h["student_id"] for h in hits}
        assert sample_student.id in ids

    async def test_propagate_on_start_idempotent(
        self, db_session: AsyncSession, sample_student, sample_user
    ):
        await self._load_process(db_session)
        extra = _seed_ta_passes(dict(sample_student.extra_data or {}))
        sample_student.extra_data = extra
        flag_modified(sample_student, "extra_data")
        await db_session.commit()

        engine = StateMachineEngine(db_session)
        instance = await engine.start_process(
            process_code="ta_to_assistant_faculty",
            student_id=sample_student.id,
            actor_id=sample_user.id,
            actor_role="admin",
            initial_context={"course_code": COURSE_CODE},
        )
        await db_session.flush()
        instance.current_state_code = "auto_or_manual_trigger"
        flag_modified(instance, "context_data")
        await db_session.commit()

        to_state = await propagate_on_start(db_session, instance, actor_id=SYSTEM_ACTOR_ID)
        await db_session.commit()
        assert to_state == "supervision_review"
