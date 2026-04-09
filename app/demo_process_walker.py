"""
راه‌روی خودکار فرایندها برای دادهٔ دمو (محیط محصول / ادمین).

- همان بستر تست‌های سطح B/C: initial_context، merge بعد از گام اول، و mock AttendanceService
- نقش اجراکننده: admin (طبق موتور، ادمین می‌تواند همهٔ ترنزیشن‌ها را اجرا کند)
- برای ثبت‌نام آشنایی، سناریوهای صریح شاخه‌ای (پذیرش کامل، رد، مشروط، تک‌درس) جدا از ماتریس کلی
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any, Callable, Optional

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.auth import get_password_hash
from app.core.engine import StateMachineEngine
from app.demo_role_users import DemoActors, build_demo_actors, ensure_demo_role_users
from app.models.operational_models import FinancialRecord, ProcessInstance, Student, User
from app.services.attendance_service import AttendanceService

logger = logging.getLogger(__name__)

METADATA_PROCESSES_DIR = Path(__file__).resolve().parent.parent / "metadata" / "processes"

PROCESSES_WITH_NO_TRANSITIONS = frozenset({"process_merged_to_one"})

# هم‌تراز tests/processes/test_all_processes_level_b.py
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
    "live_therapy_observation_course_completion": {"grades_submitted_before_sla": True},
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
}

# هم‌تراز tests/processes/test_all_processes_level_c.py
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

_DEFAULT_PAYLOAD_TRIES: list[dict[str, Any] | None] = [
    None,
    {},
    {"payment_method": "cash"},
    {"payment_method": "installment", "installment_count": 4},
]

_EXTRA_PAYLOAD_TRIES: list[dict[str, Any] | None] = [
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
    {"selected_timeslot": "2026-04-10T10:00:00"},
    {"documents_complete": True},
    {"lms_login": True},
    {"selected_courses": ["theory_1", "theory_2"], "admission_type": "full"},
]

_DEPRIORITIZED_TRIGGERS = frozenset({"payment_failed", "application_withdrawn", "withdraw"})

_attendance_orig: dict[str, Any] = {}


def apply_demo_attendance_patches() -> None:
    """مقادیر پایدار برای قوانین سهمیه/ساعت (مثل monkeypatch تست‌ها)."""
    global _attendance_orig
    if _attendance_orig:
        return

    async def _quota(self: AttendanceService, student_id: uuid.UUID) -> int:
        return 6

    async def _abs_count(self: AttendanceService, student_id: uuid.UUID, **kwargs: Any) -> int:
        return 0

    async def _hours(self: AttendanceService, student_id: uuid.UUID) -> dict:
        return {"total_hours": 100}

    async def _hours_until_slot(self: AttendanceService, student_id: uuid.UUID) -> float:
        return 24.0

    for name, repl in (
        ("calculate_absence_quota", _quota),
        ("get_absence_count", _abs_count),
        ("get_completed_hours", _hours),
        ("get_hours_until_first_slot", _hours_until_slot),
    ):
        _attendance_orig[name] = getattr(AttendanceService, name)
        setattr(AttendanceService, name, repl)


def restore_demo_attendance_patches() -> None:
    global _attendance_orig
    for name, orig in _attendance_orig.items():
        setattr(AttendanceService, name, orig)
    _attendance_orig.clear()


def _sort_avail(avail: list[dict]) -> list[dict]:
    first = [a for a in avail if a.get("trigger_event") not in _DEPRIORITIZED_TRIGGERS]
    last = [a for a in avail if a.get("trigger_event") in _DEPRIORITIZED_TRIGGERS]
    return first + last


def _expand_payload_variants(
    trigger: str,
    current_state: str,
    process_code: str,
) -> list[dict[str, Any] | None]:
    base: list[dict[str, Any] | None] = []
    base.extend(_DEFAULT_PAYLOAD_TRIES)
    base.extend(_EXTRA_PAYLOAD_TRIES)

    if trigger == "interview_result_submitted":
        base.extend(
            [
                {
                    "interview_result": "full_admission",
                    "to_state": "result_full_admission",
                    "allowed_course_count": 5,
                },
                {
                    "interview_result": "conditional_therapy",
                    "to_state": "result_conditional_therapy",
                },
                {
                    "interview_result": "single_course",
                    "to_state": "result_single_course",
                },
                {"interview_result": "rejected", "to_state": "rejected"},
            ]
        )

    if process_code == "introductory_course_registration" and current_state == "course_selection":
        base.extend(
            [
                {"selected_courses": ["theory_1", "theory_2"], "admission_type": "full"},
                {"selected_courses": ["theory_1"], "admission_type": "single_course"},
            ]
        )

    if trigger == "absence_excused":
        base.extend([{"absence_excused": True}, {"absence_type": "mutual"}])
    if trigger == "absence_unexcused":
        base.extend([{"absence_excused": False}])

    if trigger == "day_time_entered":
        base.extend(
            [
                {"proposed_day": "saturday", "proposed_time": "10:00"},
                {"day_time": "2026-04-15T10:00:00"},
            ]
        )

    seen: set[str] = set()
    out: list[dict[str, Any] | None] = []
    for p in base:
        key = repr(p)
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


async def greedy_walk_process(
    engine: StateMachineEngine,
    db: AsyncSession,
    instance_id: uuid.UUID,
    process_json: dict[str, Any],
    admin_id: uuid.UUID,
    max_steps: int = 200,
) -> tuple[bool, str, int, str]:
    """
    تا ترمینال یا حداکثر گام، با ترنزیشن‌های موجود برای admin جلو می‌رود.

    Returns:
        (ok, final_state_or_message, steps_used, status: completed|stuck|max_steps)
    """
    proc = process_json.get("process") or {}
    code = proc.get("code") or ""
    merge_applied = False
    step_count = 0
    state_visits: dict[str, int] = {}

    while step_count < max_steps:
        inst = await engine.get_process_instance(instance_id)
        if inst.is_completed or inst.is_cancelled:
            return True, inst.current_state_code, step_count, "completed"

        cur_state = inst.current_state_code
        state_visits[cur_state] = state_visits.get(cur_state, 0) + 1
        if state_visits[cur_state] > 35:
            return False, cur_state, step_count, "cycle"

        if not merge_applied and step_count >= 1:
            merge = LEVEL_C_CONTEXT_MERGE_AFTER_STEP1.get(code)
            if merge:
                ctx = dict(inst.context_data or {})
                ctx.update(merge)
                inst.context_data = ctx
                flag_modified(inst, "context_data")
                await db.commit()
            merge_applied = True

        avail = _sort_avail(await engine.get_available_transitions(instance_id, "admin"))
        if not avail:
            return False, inst.current_state_code, step_count, "stuck"

        progressed = False
        for trans in avail:
            trigger = trans["trigger_event"]
            for payload in _expand_payload_variants(trigger, inst.current_state_code, code):
                result = await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event=trigger,
                    actor_id=admin_id,
                    actor_role="admin",
                    payload=payload,
                )
                await db.commit()
                if result.success:
                    progressed = True
                    step_count += 1
                    break
            if progressed:
                break

        if not progressed:
            inst2 = await engine.get_process_instance(instance_id)
            return False, inst2.current_state_code, step_count, "stuck"

    inst = await engine.get_process_instance(instance_id)
    return False, inst.current_state_code, step_count, "max_steps"


def _student_extra_for_demo() -> dict[str, Any]:
    return {
        "is_suspended": False,
        "admission_type": "full_admission",
        "has_active_therapist": True,
        "introductory_courses_passed_count": 10,
        "demo_matrix_seed": True,
    }


def _course_type_for_process_code(code: str) -> str:
    if code in (
        "comprehensive_course_registration",
        "therapy_session_increase",
        "supervision_session_increase",
    ) or code.startswith("comprehensive_"):
        return "comprehensive"
    return "introductory"


async def ensure_admin_for_matrix_seed(db: AsyncSession) -> User:
    """
    همان منطق app.main._ensure_admin_user: همیشه می‌توان با admin / admin123
    (بعد از تب «ورود با رمز عبور» و پاسخ به چالش امنیتی) وارد پنل شد.
    """
    from app.api.auth import verify_password

    result = await db.execute(select(User).where(User.username == "admin"))
    admin = result.scalars().first()
    if admin:
        try:
            ok = admin.hashed_password and verify_password("admin123", admin.hashed_password)
        except Exception:
            ok = False
        if not ok:
            admin.hashed_password = get_password_hash("admin123")
            admin.is_active = True
            admin.role = "admin"
            await db.commit()
            logger.info("Admin password reset to admin123 (matrix seed)")
        await db.refresh(admin)
        return admin

    admin = User(
        id=uuid.uuid4(),
        username="admin",
        email="admin@anistito.ir",
        hashed_password=get_password_hash("admin123"),
        full_name_fa="مدیر سیستم",
        role="admin",
        is_active=True,
    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    logger.info("Default admin created: username=admin, password=admin123")
    return admin


async def delete_demo_seed_users(
    db: AsyncSession,
    prefixes: tuple[str, ...] = ("AUTO-DEMO-", "DEMO-SCEN-"),
) -> int:
    """حذف دانشجو/کاربر دمو قبلی (کد دانشجویی با یکی از پیشوندها)."""
    if not prefixes:
        return 0
    conds = [Student.student_code.startswith(p) for p in prefixes]
    stmt = select(Student).where(or_(*conds) if len(conds) > 1 else conds[0])
    r = await db.execute(stmt)
    rows = list(r.scalars().all())
    n = 0
    for st in rows:
        await db.execute(delete(ProcessInstance).where(ProcessInstance.student_id == st.id))
        await db.execute(delete(FinancialRecord).where(FinancialRecord.student_id == st.id))
        uid = st.user_id
        await db.delete(st)
        ur = await db.execute(select(User).where(User.id == uid))
        u = ur.scalars().first()
        if u:
            await db.delete(u)
        n += 1
    await db.commit()
    return n


async def create_demo_student(
    db: AsyncSession,
    student_code: str,
    username: str,
    full_name_fa: str,
    password: str,
    course_type: str,
) -> tuple[User, Student]:
    r = await db.execute(select(User).where(User.username == username))
    existing_u = r.scalars().first()
    if existing_u:
        r2 = await db.execute(select(Student).where(Student.user_id == existing_u.id))
        st = r2.scalars().first()
        if st:
            st.student_code = student_code
            st.course_type = course_type
            st.is_sample_data = True
            st.extra_data = _student_extra_for_demo()
            flag_modified(st, "extra_data")
            existing_u.full_name_fa = full_name_fa
            existing_u.hashed_password = get_password_hash(password)
            await db.commit()
            await db.refresh(st)
            return existing_u, st

    u = User(
        id=uuid.uuid4(),
        username=username,
        email=f"{username}@demo-matrix.local",
        hashed_password=get_password_hash(password),
        full_name_fa=full_name_fa,
        role="student",
        is_active=True,
    )
    db.add(u)
    await db.flush()
    st = Student(
        id=uuid.uuid4(),
        user_id=u.id,
        student_code=student_code,
        course_type=course_type,
        is_intern=False,
        term_count=4,
        current_term=1,
        weekly_sessions=1,
        therapy_started=False,
        is_sample_data=True,
        extra_data=_student_extra_for_demo(),
    )
    db.add(st)
    await db.commit()
    await db.refresh(u)
    await db.refresh(st)
    return u, st


async def run_scenario_intro_full(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: DemoActors,
    student_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> None:
    """مسیر tests/e2e: ثبت‌نام آشنایی تا registration_complete سپس introductory_course_completion."""
    reg = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=student_id,
        actor_id=actors.applicant_id,
        actor_role="applicant",
    )
    await db.commit()

    for trigger, role, uid, payload in [
        ("timeslot_selected", "applicant", actors.applicant_id, {"selected_timeslot": "2026-04-10T10:00:00"}),
        ("proceed_to_payment", "applicant", actors.applicant_id, None),
        ("payment_success", "applicant", actors.applicant_id, None),
        ("interview_time_reached", "admin", actors.admin_id, None),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=uid,
            actor_role=role,
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro full: {trigger} -> {r.error}")

    r = await engine.execute_transition(
        instance_id=reg.id,
        trigger_event="interview_result_submitted",
        actor_id=actors.interviewer_id,
        actor_role="interviewer",
        payload={
            "interview_result": "full_admission",
            "to_state": "result_full_admission",
            "allowed_course_count": 5,
        },
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"intro full: interview_result_submitted -> {r.error}")

    for trigger, role, uid, payload in [
        ("proceed_to_documents", "admin", actors.admin_id, None),
        ("documents_submitted", "applicant", actors.applicant_id, {"documents_complete": True}),
        ("documents_approved", "admissions_officer", actors.admissions_id, None),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=uid,
            actor_role=role,
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro full: {trigger} -> {r.error}")

    for trigger, payload in [
        ("student_logged_in", {"lms_login": True}),
        ("courses_selected", {"selected_courses": ["theory_1", "theory_2"], "admission_type": "full"}),
        ("payment_completed", {"payment_method": "cash"}),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=student_user_id,
            actor_role="student",
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro full: {trigger} -> {r.error}")

    completion = await engine.start_process(
        process_code="introductory_course_completion",
        student_id=student_id,
        actor_id=actors.admin_id,
        actor_role="system",
    )
    await db.commit()

    for trigger, role in [
        ("all_10_courses_passed", "system"),
        ("generate_certificate_draft", "system"),
        ("draft_ready_for_review", "system"),
        ("committee_approved_certificate", "admin"),
        ("student_notified", "system"),
    ]:
        r = await engine.execute_transition(
            instance_id=completion.id,
            trigger_event=trigger,
            actor_id=actors.admin_id,
            actor_role=role,
            payload=None,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro completion: {trigger} -> {r.error}")


async def run_scenario_intro_rejected(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: DemoActors,
    student_id: uuid.UUID,
) -> None:
    reg = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=student_id,
        actor_id=actors.applicant_id,
        actor_role="applicant",
    )
    await db.commit()

    for trigger, role, uid, payload in [
        ("timeslot_selected", "applicant", actors.applicant_id, {"selected_timeslot": "2026-04-11T14:00:00"}),
        ("proceed_to_payment", "applicant", actors.applicant_id, None),
        ("payment_success", "applicant", actors.applicant_id, None),
        ("interview_time_reached", "admin", actors.admin_id, None),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=uid,
            actor_role=role,
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro reject: {trigger} -> {r.error}")

    r = await engine.execute_transition(
        instance_id=reg.id,
        trigger_event="interview_result_submitted",
        actor_id=actors.interviewer_id,
        actor_role="interviewer",
        payload={"interview_result": "rejected", "to_state": "rejected"},
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"intro reject: interview_result_submitted -> {r.error}")


async def run_scenario_intro_conditional(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: DemoActors,
    student_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> None:
    reg = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=student_id,
        actor_id=actors.applicant_id,
        actor_role="applicant",
    )
    await db.commit()

    for trigger, role, uid, payload in [
        ("timeslot_selected", "applicant", actors.applicant_id, {"selected_timeslot": "2026-04-12T09:00:00"}),
        ("proceed_to_payment", "applicant", actors.applicant_id, None),
        ("payment_success", "applicant", actors.applicant_id, None),
        ("interview_time_reached", "admin", actors.admin_id, None),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=uid,
            actor_role=role,
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro cond: {trigger} -> {r.error}")

    r = await engine.execute_transition(
        instance_id=reg.id,
        trigger_event="interview_result_submitted",
        actor_id=actors.interviewer_id,
        actor_role="interviewer",
        payload={
            "interview_result": "conditional_therapy",
            "to_state": "result_conditional_therapy",
        },
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"intro cond: interview -> {r.error}")

    sr = await db.execute(select(Student).where(Student.id == student_id))
    _st = sr.scalars().first()
    if _st:
        ex = dict(_st.extra_data or {})
        ex["admission_type"] = "conditional_therapy"
        _st.extra_data = ex
        flag_modified(_st, "extra_data")
        await db.commit()

    for trigger, role, uid, payload in [
        ("proceed_to_documents", "admin", actors.admin_id, None),
        ("documents_submitted", "applicant", actors.applicant_id, {"documents_complete": True}),
        ("documents_approved", "admissions_officer", actors.admissions_id, None),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=uid,
            actor_role=role,
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro cond: {trigger} -> {r.error}")

    for trigger, payload in [
        ("student_logged_in", {"lms_login": True}),
        ("courses_selected", {"selected_courses": ["theory_1"], "admission_type": "conditional_therapy"}),
        ("payment_completed", {"payment_method": "cash"}),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=student_user_id,
            actor_role="student",
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro cond: {trigger} -> {r.error}")


async def run_scenario_intro_single_course(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: DemoActors,
    student_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> None:
    reg = await engine.start_process(
        process_code="introductory_course_registration",
        student_id=student_id,
        actor_id=actors.applicant_id,
        actor_role="applicant",
    )
    await db.commit()

    for trigger, role, uid, payload in [
        ("timeslot_selected", "applicant", actors.applicant_id, {"selected_timeslot": "2026-04-13T11:00:00"}),
        ("proceed_to_payment", "applicant", actors.applicant_id, None),
        ("payment_success", "applicant", actors.applicant_id, None),
        ("interview_time_reached", "admin", actors.admin_id, None),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=uid,
            actor_role=role,
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro single: {trigger} -> {r.error}")

    r = await engine.execute_transition(
        instance_id=reg.id,
        trigger_event="interview_result_submitted",
        actor_id=actors.interviewer_id,
        actor_role="interviewer",
        payload={
            "interview_result": "single_course",
            "to_state": "result_single_course",
        },
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"intro single: interview -> {r.error}")

    sr = await db.execute(select(Student).where(Student.id == student_id))
    _st = sr.scalars().first()
    if _st:
        ex = dict(_st.extra_data or {})
        ex["admission_type"] = "single_course"
        _st.extra_data = ex
        flag_modified(_st, "extra_data")
        await db.commit()

    for trigger, role, uid, payload in [
        ("proceed_to_documents", "admin", actors.admin_id, None),
        ("documents_submitted", "applicant", actors.applicant_id, {"documents_complete": True}),
        ("documents_approved", "admissions_officer", actors.admissions_id, None),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=uid,
            actor_role=role,
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro single: {trigger} -> {r.error}")

    for trigger, payload in [
        ("student_logged_in", {"lms_login": True}),
        ("courses_selected", {"selected_courses": ["theory_1"], "admission_type": "single_course"}),
        ("payment_completed", {"payment_method": "cash"}),
    ]:
        r = await engine.execute_transition(
            instance_id=reg.id,
            trigger_event=trigger,
            actor_id=student_user_id,
            actor_role="student",
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"intro single: {trigger} -> {r.error}")


async def run_scenario_term2_therapy_failed(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: DemoActors,
    student_id: uuid.UUID,
) -> None:
    """شاخهٔ توقف: مشروط به درمان بدون درمانگر فعال."""
    sr = await db.execute(select(Student).where(Student.id == student_id))
    st = sr.scalars().first()
    if not st:
        raise RuntimeError("term2 therapy: student not found")
    ex = dict(_student_extra_for_demo())
    ex["admission_type"] = "conditional_therapy"
    ex["has_active_therapist"] = False
    ex["is_suspended"] = False
    st.extra_data = ex
    flag_modified(st, "extra_data")
    await db.commit()

    inst = await engine.start_process(
        process_code="intro_second_semester_registration",
        student_id=student_id,
        actor_id=actors.admin_id,
        actor_role="system",
    )
    await db.commit()
    r = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="eligibility_check_result",
        actor_id=actors.admin_id,
        actor_role="admin",
        payload={},
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"term2 therapy failed branch: {r.error}")


async def run_scenario_term2_suspension(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: DemoActors,
    student_id: uuid.UUID,
) -> None:
    """شاخهٔ توقف: تعلیق آموزشی."""
    sr = await db.execute(select(Student).where(Student.id == student_id))
    st = sr.scalars().first()
    if not st:
        raise RuntimeError("term2 susp: student not found")
    ex = dict(_student_extra_for_demo())
    ex["admission_type"] = "full_admission"
    ex["has_active_therapist"] = True
    ex["is_suspended"] = True
    st.extra_data = ex
    flag_modified(st, "extra_data")
    await db.commit()

    inst = await engine.start_process(
        process_code="intro_second_semester_registration",
        student_id=student_id,
        actor_id=actors.admin_id,
        actor_role="system",
    )
    await db.commit()
    r = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="eligibility_check_result",
        actor_id=actors.admin_id,
        actor_role="admin",
        payload={},
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"term2 suspension branch: {r.error}")


async def run_scenario_term2_cash(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: DemoActors,
    student_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> None:
    """ترم دوم — پرداخت نقدی تا بستن نمونه (term2_registration_closed)."""
    sr = await db.execute(select(Student).where(Student.id == student_id))
    st = sr.scalars().first()
    if not st:
        raise RuntimeError("term2 cash: student not found")
    ex = dict(_student_extra_for_demo())
    ex.setdefault("admission_type", "full_admission")
    ex["is_suspended"] = False
    ex["has_active_therapist"] = True
    st.extra_data = ex
    flag_modified(st, "extra_data")
    await db.commit()

    inst = await engine.start_process(
        process_code="intro_second_semester_registration",
        student_id=student_id,
        actor_id=actors.admin_id,
        actor_role="system",
    )
    await db.commit()

    r = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="eligibility_check_result",
        actor_id=actors.admin_id,
        actor_role="admin",
        payload={},
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"term2 cash eligibility: {r.error}")

    for trigger, payload in [
        ("courses_confirmed", {"courses": ["تئوری روانکاوی ۲"]}),
        ("payment_method_selected", {"payment_method": "cash"}),
        ("payment_completed", {"payment_method": "cash"}),
    ]:
        r = await engine.execute_transition(
            instance_id=inst.id,
            trigger_event=trigger,
            actor_id=student_user_id,
            actor_role="student",
            payload=payload,
        )
        await db.commit()
        if not r.success:
            raise RuntimeError(f"term2 cash {trigger}: {r.error}")


async def run_scenario_term2_installment(
    engine: StateMachineEngine,
    db: AsyncSession,
    actors: DemoActors,
    student_user_id: uuid.UUID,
    student_id: uuid.UUID,
) -> None:
    """ترم دوم — اولین قسط اقساطی؛ نمونه در registration_complete با اقساط باقی‌مانده."""
    sr = await db.execute(select(Student).where(Student.id == student_id))
    st = sr.scalars().first()
    if not st:
        raise RuntimeError("term2 inst: student not found")
    ex = dict(_student_extra_for_demo())
    ex.setdefault("admission_type", "full_admission")
    ex["is_suspended"] = False
    ex["has_active_therapist"] = True
    st.extra_data = ex
    flag_modified(st, "extra_data")
    await db.commit()

    inst = await engine.start_process(
        process_code="intro_second_semester_registration",
        student_id=student_id,
        actor_id=actors.admin_id,
        actor_role="system",
    )
    await db.commit()

    r = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="eligibility_check_result",
        actor_id=actors.admin_id,
        actor_role="admin",
        payload={},
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"term2 inst eligibility: {r.error}")

    r = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="courses_confirmed",
        actor_id=student_user_id,
        actor_role="student",
        payload={"courses": ["تئوری روانکاوی ۲"]},
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"term2 inst courses: {r.error}")

    r = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="payment_method_selected",
        actor_id=student_user_id,
        actor_role="student",
        payload={"payment_method": "installment", "installment_count": 4},
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"term2 inst payment_method: {r.error}")

    r = await engine.execute_transition(
        instance_id=inst.id,
        trigger_event="payment_completed",
        actor_id=student_user_id,
        actor_role="student",
        payload={"payment_method": "installment", "installment_count": 4},
    )
    await db.commit()
    if not r.success:
        raise RuntimeError(f"term2 inst payment_completed: {r.error}")


SCENARIO_RUNNERS: dict[str, Callable[..., Any]] = {
    "intro_full": run_scenario_intro_full,
    "intro_rejected": run_scenario_intro_rejected,
    "intro_conditional": run_scenario_intro_conditional,
    "intro_single_course": run_scenario_intro_single_course,
    "term2_therapy_failed": run_scenario_term2_therapy_failed,
    "term2_suspension": run_scenario_term2_suspension,
    "term2_cash": run_scenario_term2_cash,
    "term2_installment": run_scenario_term2_installment,
}

SCENARIO_LABELS: dict[str, tuple[str, str, str]] = {
    "intro_full": (
        "DEMO-SCEN-INTRO-FULL",
        "auto_scen_intro_full",
        "سناریو: ثبت‌نام آشنایی تا پایان دوره (پذیرش کامل + گواهی)",
    ),
    "intro_rejected": (
        "DEMO-SCEN-INTRO-REJECT",
        "auto_scen_intro_reject",
        "سناریو: رد مصاحبه (ترمینال rejected)",
    ),
    "intro_conditional": (
        "DEMO-SCEN-INTRO-COND",
        "auto_scen_intro_cond",
        "سناریو: پذیرش مشروط به درمان",
    ),
    "intro_single_course": (
        "DEMO-SCEN-INTRO-SINGLE",
        "auto_scen_intro_single",
        "سناریو: پذیرش تک‌درس",
    ),
    "term2_therapy_failed": (
        "DEMO-SCEN-TERM2-NOTHER",
        "auto_scen_term2_notherapist",
        "سناریو: ترم دوم — توقف (مشروط بدون درمانگر فعال)",
    ),
    "term2_suspension": (
        "DEMO-SCEN-TERM2-SUSP",
        "auto_scen_term2_susp",
        "سناریو: ترم دوم — توقف (تعلیق آموزشی)",
    ),
    "term2_cash": (
        "DEMO-SCEN-TERM2-CASH",
        "auto_scen_term2_cash",
        "سناریو: ترم دوم — پرداخت نقدی تا بستن فرایند",
    ),
    "term2_installment": (
        "DEMO-SCEN-TERM2-INST",
        "auto_scen_term2_inst",
        "سناریو: ترم دوم — قسط اول اقساطی (نمونه باز با اقساط مانده)",
    ),
}


def list_process_json_files() -> list[Path]:
    return sorted(METADATA_PROCESSES_DIR.glob("*.json"))


async def seed_full_matrix(
    db: AsyncSession,
    load_rules_fn,
    load_process_fn,
    demo_password: str,
) -> dict[str, Any]:
    """
    برای هر فایل JSON: sync متادیتا، یک دانشجوی AUTO-DEMO-{code}، start + greedy walk.
    """
    from app.meta.seed import load_process as _load_process, load_rules as _load_rules

    load_rules_fn = load_rules_fn or _load_rules
    load_process_fn = load_process_fn or _load_process

    apply_demo_attendance_patches()
    try:
        await load_rules_fn(db)
        for pf in list_process_json_files():
            await load_process_fn(db, pf)
        await db.commit()

        await ensure_demo_role_users(db)
        admin = await ensure_admin_for_matrix_seed(db)
        admin_id = admin.id

        engine = StateMachineEngine(db)
        report: dict[str, Any] = {
            "processes": {},
            "ok_count": 0,
            "stuck_count": 0,
            "admin_login": {
                "username": "admin",
                "password": "admin123",
                "ui_note": "Use password tab (not SMS); solve the math challenge; then submit.",
            },
        }

        for pf in list_process_json_files():
            with open(pf, encoding="utf-8") as f:
                data = json.load(f)
            proc = data.get("process") or {}
            code = proc.get("code")
            if not code:
                continue

            if code in PROCESSES_WITH_NO_TRANSITIONS:
                u, st = await create_demo_student(
                    db,
                    student_code=f"AUTO-DEMO-{code}"[:50],
                    username=f"auto_demo_{code}"[:90],
                    full_name_fa=f"نمونه آموزشی (بدون ترنزیشن) — {code}",
                    password=demo_password,
                    course_type=_course_type_for_process_code(code),
                )
                await engine.start_process(
                    process_code=code,
                    student_id=st.id,
                    actor_id=admin_id,
                    actor_role="admin",
                    initial_context=LEVEL_B_INITIAL_CONTEXT.get(code) or None,
                )
                await db.commit()
                report["processes"][code] = {
                    "student_code": st.student_code,
                    "status": "stub_only_started",
                }
                report["ok_count"] += 1
                continue

            u, st = await create_demo_student(
                db,
                student_code=f"AUTO-DEMO-{code}"[:50],
                username=f"auto_demo_{code}"[:90],
                full_name_fa=f"نمونه آموزشی — {proc.get('name_fa') or code}",
                password=demo_password,
                course_type=_course_type_for_process_code(code),
            )

            start_ctx = dict(LEVEL_B_INITIAL_CONTEXT.get(code, {}))
            inst = await engine.start_process(
                process_code=code,
                student_id=st.id,
                actor_id=admin_id,
                actor_role="admin",
                initial_context=start_ctx or None,
            )
            await db.commit()

            ok, final_state, steps, status = await greedy_walk_process(
                engine, db, inst.id, data, admin_id
            )
            report["processes"][code] = {
                "student_code": st.student_code,
                "username": u.username,
                "completed": ok,
                "final_state": final_state,
                "steps": steps,
                "walk_status": status,
            }
            if ok:
                report["ok_count"] += 1
            else:
                report["stuck_count"] += 1

        from app.demo_financial_seed import ensure_demo_financial_records

        n_fin = await ensure_demo_financial_records(db)
        if n_fin:
            report["demo_financial_records_seeded"] = n_fin

        return report
    finally:
        restore_demo_attendance_patches()


async def seed_branch_scenarios(
    db: AsyncSession,
    load_rules_fn,
    load_process_fn,
    demo_password: str,
) -> dict[str, str]:
    from app.meta.seed import load_process as _load_process, load_rules as _load_rules

    load_rules_fn = load_rules_fn or _load_rules
    load_process_fn = load_process_fn or _load_process

    apply_demo_attendance_patches()
    try:
        await load_rules_fn(db)
        for pf in list_process_json_files():
            await load_process_fn(db, pf)
        await db.commit()

        actors = await build_demo_actors(db)
        await ensure_admin_for_matrix_seed(db)
        engine = StateMachineEngine(db)
        out: dict[str, str] = {
            "_admin_login": "admin / admin123 — password tab + math challenge (not SMS)",
            "_panel_users": "همهٔ نقش‌ها + demo_interviewer / demo_admissions / demo_applicant — رمز غیرادمین: demo123",
        }

        _no_student_user = frozenset({"intro_rejected", "term2_therapy_failed", "term2_suspension"})

        for key, runner in SCENARIO_RUNNERS.items():
            code, uname, label = SCENARIO_LABELS[key]
            u, st = await create_demo_student(
                db,
                student_code=code[:50],
                username=uname[:90],
                full_name_fa=label,
                password=demo_password,
                course_type="introductory",
            )
            if key in _no_student_user:
                await runner(engine, db, actors, st.id)
            else:
                await runner(engine, db, actors, u.id, st.id)
            out[key] = code
            logger.info("Scenario %s OK: %s", key, code)

        from app.demo_financial_seed import ensure_demo_financial_records

        n_fin = await ensure_demo_financial_records(db)
        if n_fin:
            out["_demo_financial_records"] = str(n_fin)

        return out
    finally:
        restore_demo_attendance_patches()
