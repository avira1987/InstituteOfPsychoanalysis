"""
تست سطح B: پس از start، حداقل یک ترنزیشن از state اول (با نقش admin) دیده می‌شود
و یک ترنزیشن با موفقیت اجرا می‌شود — با initial_context و extra_data دانشجو و
در صورت نیاز mock سرویس حضور برای فیلدهای instance در موتور.

فرایندهای بدون یال (مثل stub) جداگانه بررسی می‌شوند.
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


# فرایندهایی که عمداً هیچ transition ندارند (stub متادیتا)
PROCESSES_WITH_NO_TRANSITIONS = frozenset({"process_merged_to_one"})

# initial_context برای start_process — کلیدها در instance.context_data و rule evaluation
LEVEL_B_INITIAL_CONTEXT: dict[str, dict[str, Any]] = {
    "attendance_tracking": {
        "session_paid": True,
        "student_on_leave": False,
        "session_cancelled": False,
    },
    "supervision_50h_completion": {
        "supervision_session_paid": True,
        "student_on_supervision_leave": False,
        "session_cancelled": False,
    },
    "comprehensive_course_registration": {},
    "theory_course_completion": {"grades_submitted_before_sla": True},
    "skills_course_completion": {"grades_submitted_before_sla": True},
    "film_observation_course_completion": {"grades_submitted_before_sla": True},
    "group_supervision_course_completion": {"grades_submitted_before_sla": True},
    "live_supervision_course_completion": {"grades_submitted_before_sla": True},
    "live_supervision_session_prep": {},
    "article_writing_completion": {},
    "thesis_defense_request": {},
    "upgrade_to_educational_therapist": {},
    "intern_bulk_patient_referral": {},
    "live_supervision_ta_evaluation": {},
    "live_therapy_observation_course_completion": {"grades_submitted_before_sla": True},
    "live_therapy_observation_session_prep": {},
    "live_therapy_observation_ta_attendance_completion": {"grades_submitted_before_sla": True},
    "fee_determination": {"session_paid": True},
    "student_session_cancellation": {"would_exceed_consecutive_weeks": False},
    "supervision_block_transition": {"current_supervision_block_attendance": 50},
    "supervision_session_reduction": {"supervision_weekly_sessions": 2},
    "therapy_session_reduction": {"weekly_sessions": 2},
    "therapy_completion": {
        "therapy_hours_2x": 0,
        "therapy_threshold": 250,
        "clinical_hours": 0,
        "clinical_threshold": 750,
        "supervision_hours": 0,
        "supervision_threshold": 150,
    },
    "therapy_early_termination": {"termination_reason_code": 1},
    "unannounced_absence_reaction": {
        "student_on_leave": False,
        "consecutive_unannounced_count": 1,
    },
    "therapy_changes": {"change_type": "therapist_change"},
}


def _initial_state_transitions_sorted(data: dict, initial: str) -> list[dict]:
    rows = [t for t in data.get("transitions", []) if t.get("from") == initial]
    rows.sort(key=lambda t: (-(t.get("priority") or 0), t.get("trigger", ""), t.get("to", "")))
    return rows


def _unique_triggers_in_order(rows: list[dict]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for t in rows:
        tr = t.get("trigger")
        if tr and tr not in seen:
            seen.add(tr)
            out.append(tr)
    return out


_DEFAULT_PAYLOAD_TRIES: list[dict[str, Any] | None] = [
    None,
    {},
    {"payment_method": "cash"},
    {"payment_method": "installment", "installment_count": 4},
]


@pytest.fixture(autouse=True)
def _patch_attendance_for_level_b(monkeypatch: pytest.MonkeyPatch):
    """مقادیر عددی پایدار برای قوانین سهمیه غیبت و ساعات در context موتور."""

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
async def sample_student_level_b(db_session: AsyncSession, sample_student: Student) -> Student:
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


@pytest.mark.asyncio
@pytest.mark.parametrize("process_file", _process_json_paths(), ids=lambda p: p.stem)
async def test_process_level_b_one_transition_from_initial_succeeds(
    db_session: AsyncSession,
    sample_student_level_b: Student,
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
        student_id=sample_student_level_b.id,
        actor_id=sample_user.id,
        actor_role="admin",
        initial_context=start_ctx or None,
    )
    await db_session.commit()

    available = await engine.get_available_transitions(instance.id, "admin")

    if code in PROCESSES_WITH_NO_TRANSITIONS:
        assert len(available) == 0, f"{code}: stub فرایند نباید ترنزیشن داشته باشد"
        assert not data.get("transitions"), f"{code}: JSON باید transitions خالی باشد"
        return

    assert len(available) >= 1, (
        f"{code}: هیچ ترنزیشنی از state اول «{initial}» برای admin دیده نمی‌شود"
    )

    initial_rows = _initial_state_transitions_sorted(data, initial)
    triggers = _unique_triggers_in_order(initial_rows)
    assert triggers, f"{code}: در JSON هیچ ترنزی از {initial} تعریف نشده"

    last_error = ""
    for trigger in triggers:
        for raw_payload in _DEFAULT_PAYLOAD_TRIES:
            payload = dict(raw_payload) if raw_payload is not None else {}
            result = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event=trigger,
                actor_id=sample_user.id,
                actor_role="admin",
                payload=payload,
            )
            await db_session.commit()
            if result.success:
                assert result.to_state is not None
                return
            last_error = result.error or "success=False"

    pytest.fail(
        f"{code}: هیچ ترنزیشنی از state اول با payloadهای پیش‌فرض موفق نشد. آخرین خطا: {last_error}"
    )


def test_level_b_process_count_matches_metadata():
    assert len(_process_json_paths()) == EXPECTED_PROCESS_JSON_COUNT
