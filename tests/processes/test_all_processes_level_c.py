"""
تست سطح C: پس از یک ترنزیشن موفق از state اول (همان بستر سطح B)،
اگر نمونه هنوز تمام نشده، حداقل یک ترنزیشن دوم از state جدید باید موفق شود.
اگر پس از گام اول به terminal برسیم، سطح C برآورده است.

فرایند stub بدون ترنزیشن همان استثناء سطح B است.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.meta.seed import load_process, load_rules
from app.models.operational_models import Student
from app.services.attendance_service import AttendanceService

from tests.processes.test_all_processes_level_a_smoke import (
    EXPECTED_PROCESS_JSON_COUNT,
    _process_json_paths,
)
from tests.processes.test_all_processes_level_b import (
    LEVEL_B_INITIAL_CONTEXT,
    PROCESSES_WITH_NO_TRANSITIONS,
    _initial_state_transitions_sorted,
    _unique_triggers_in_order,
)

# payloadهای اضافه برای گام دوم (فرم‌ها / پرداخت / تایید)
_DEFAULT_PAYLOAD_TRIES: list[dict[str, Any] | None] = [
    None,
    {},
    {"payment_method": "cash"},
    {"payment_method": "installment", "installment_count": 4},
    {"courses_confirmed": True},
    {"payment_method_selected": True, "payment_method": "cash"},
    {"student_confirms": True},
    {"eligibility_check_result": True},
    {"type_therapist_change": True},
    {"time_registered": True},
    {"payment_success_new_block_first": True},
    {"sessions_selected": True},
    {"result_pass": True},
    {"absence_count_5": True},
]

# پس از گام اول، فیلدهای instance برای قوانین گام دوم (شبیه دادهٔ واقعی فرم/API)
LEVEL_C_CONTEXT_MERGE_AFTER_STEP1: dict[str, dict[str, Any]] = {
    "student_session_cancellation": {"cancellation_percent_after": 5},
    "class_attendance": {"student_absence_count": 5},
    "live_supervision_session_prep": {"session_time_registered": True},
    "live_therapy_observation_session_prep": {"session_time_registered": True},
    "live_supervision_ta_evaluation": {"ta_final_score": 80},
    "supervision_block_transition": {"selected_supervision_weekly_count": 1},
    "supervision_session_reduction": {"supervision_remaining_after_reduction": 2},
    "therapy_changes": {"change_type": "therapist_change"},
    "therapy_session_reduction": {"remaining_sessions_after_reduction": 3},
}


@pytest.fixture(autouse=True)
def _patch_attendance_for_level_c(monkeypatch: pytest.MonkeyPatch):
    async def _quota(self, student_id: UUID) -> int:
        return 6

    async def _abs_count(self, student_id: UUID, **kwargs: Any) -> int:
        return 0

    async def _hours(self, student_id: UUID) -> dict:
        return {"total_hours": 100}

    async def _hours_until_slot(self, student_id: UUID) -> float:
        return 24.0

    monkeypatch.setattr(AttendanceService, "calculate_absence_quota", _quota)
    monkeypatch.setattr(AttendanceService, "get_absence_count", _abs_count)
    monkeypatch.setattr(AttendanceService, "get_completed_hours", _hours)
    monkeypatch.setattr(AttendanceService, "get_hours_until_first_slot", _hours_until_slot)


@pytest_asyncio.fixture
async def sample_student_level_c(db_session: AsyncSession, sample_student: Student) -> Student:
    extra = dict(sample_student.extra_data or {})
    extra.setdefault("is_suspended", False)
    extra.setdefault("admission_type", "full_admission")
    extra.setdefault("has_active_therapist", True)
    extra.setdefault("introductory_courses_passed_count", 10)
    sample_student.extra_data = extra
    flag_modified(sample_student, "extra_data")
    await db_session.commit()
    await db_session.refresh(sample_student)
    return sample_student


async def _run_first_successful_transition(
    engine: StateMachineEngine,
    db_session: AsyncSession,
    instance_id: UUID,
    data: dict,
    initial: str,
    sample_user,
) -> tuple[bool, str]:
    rows = _initial_state_transitions_sorted(data, initial)
    triggers = _unique_triggers_in_order(rows)
    last_error = ""
    for trigger in triggers:
        for raw_payload in _DEFAULT_PAYLOAD_TRIES:
            payload = dict(raw_payload) if raw_payload is not None else {}
            result = await engine.execute_transition(
                instance_id=instance_id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role="admin",
                payload=payload,
            )
            await db_session.commit()
            if result.success:
                return True, ""
            last_error = result.error or "success=False"
    return False, last_error


async def _run_any_successful_transition_from_state(
    engine: StateMachineEngine,
    db_session: AsyncSession,
    instance_id: UUID,
    data: dict,
    state: str,
    sample_user,
) -> tuple[bool, str]:
    rows = _initial_state_transitions_sorted(data, state)
    triggers = _unique_triggers_in_order(rows)
    last_error = ""
    for trigger in triggers:
        for raw_payload in _DEFAULT_PAYLOAD_TRIES:
            payload = dict(raw_payload) if raw_payload is not None else {}
            result = await engine.execute_transition(
                instance_id=instance_id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role="admin",
                payload=payload,
            )
            await db_session.commit()
            if result.success:
                return True, ""
            last_error = result.error or "success=False"
    return False, last_error


@pytest.mark.asyncio
@pytest.mark.parametrize("process_file", _process_json_paths(), ids=lambda p: p.stem)
async def test_process_level_c_second_transition_or_terminal_after_first(
    db_session: AsyncSession,
    sample_student_level_c: Student,
    sample_user,
    process_file: Path,
):
    with open(process_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    proc = data.get("process") or {}
    code = proc.get("code")
    initial = proc.get("initial_state")
    assert code and initial

    await load_rules(db_session)
    await load_process(db_session, process_file)
    await db_session.commit()

    start_ctx = dict(LEVEL_B_INITIAL_CONTEXT.get(code, {}))

    engine = StateMachineEngine(db_session)
    instance = await engine.start_process(
        process_code=code,
        student_id=sample_student_level_c.id,
        actor_id=sample_user.id,
        actor_role="admin",
        initial_context=start_ctx or None,
    )
    await db_session.commit()

    if code in PROCESSES_WITH_NO_TRANSITIONS:
        assert not data.get("transitions")
        return

    ok1, err1 = await _run_first_successful_transition(
        engine, db_session, instance.id, data, initial, sample_user
    )
    assert ok1, f"{code}: گام اول ناموفق: {err1}"

    instance = await engine.get_process_instance(instance.id)
    if instance.is_completed or instance.is_cancelled:
        return

    merge = LEVEL_C_CONTEXT_MERGE_AFTER_STEP1.get(code)
    if merge:
        ctx = dict(instance.context_data or {})
        ctx.update(merge)
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db_session.commit()

    cur = instance.current_state_code
    rows2 = _initial_state_transitions_sorted(data, cur)
    assert rows2, f"{code}: پس از گام اول state={cur} هیچ ترنزیشن خروجی در JSON نیست"

    ok2, err2 = await _run_any_successful_transition_from_state(
        engine, db_session, instance.id, data, cur, sample_user
    )
    assert ok2, (
        f"{code}: گام دوم از «{cur}» ناموفق (نمونه هنوز باز است). آخرین خطا: {err2}"
    )


def test_level_c_process_count_matches_metadata():
    assert len(_process_json_paths()) == EXPECTED_PROCESS_JSON_COUNT
