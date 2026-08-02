"""
Hybrid seeder: BFS engine walk to target state, then DB fallback if unreachable.
"""

from __future__ import annotations

import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.demo_process_walker import (
    LEVEL_B_INITIAL_CONTEXT,
    LEVEL_C_CONTEXT_MERGE_AFTER_STEP1,
    _expand_payload_variants,
    apply_demo_attendance_patches,
    create_demo_student,
    ensure_admin_for_matrix_seed,
    restore_demo_attendance_patches,
)
from app.demo_role_users import ensure_demo_role_users
from app.models.operational_models import ProcessInstance, Student, User

FLOW_STUDENT_PREFIX = "FLOW-FT-"

# Known admin walk sequences (process_code -> list of (trigger, actor_role))
KNOWN_WALK_SEQUENCES: dict[str, list[tuple[str, str]]] = {
    "fall_semester_preparation": [
        ("calendar_submitted", "course_committee"),
        ("tuition_submitted", "deputy_education"),
        ("license_reviewed", "deputy_education"),
        ("course_list_submitted", "course_committee"),
        ("courses_finalized", "course_committee"),
        ("marketing_started", "staff"),
        ("interviewers_assigned", "deputy_education"),
        ("interview_times_set", "staff"),
    ],
    "winter_semester_preparation": [
        ("license_reviewed", "deputy_education"),
        ("course_list_submitted", "course_committee"),
        ("courses_finalized", "course_committee"),
        ("marketing_started", "staff"),
        ("interviewers_assigned", "deputy_education"),
        ("interview_times_set", "staff"),
    ],
}

_SAMPLE_COURSE_ROW = {
    "course_name": "theory_psychoanalysis_1",
    "track": "analytic_psychotherapy",
    "proposed_day": "شنبه",
    "proposed_time": "10:00",
    "instructor": "مدرس تست",
    "teaching_assistant": "کمک‌مدرس تست",
}


def _intro_reg_context(target_state: str) -> dict[str, Any]:
    """Minimal context for intro registration states when using db_fallback."""
    ctx: dict[str, Any] = {}
    if target_state in (
        "documents_upload",
        "documents_incomplete",
        "documents_review",
        "credentials_created",
        "course_selection",
        "payment",
    ):
        ctx.update(
            {
                "admission_type": "full",
                "allowed_course_count": 5,
                "documents_upload_deadline": "2026-12-31T23:59:59+00:00",
                "interview_result": "full_admission",
                "digital_commitment": True,
                "photo": {"file_name": "flow_test.jpg", "url": "/uploads/flow_test.jpg"},
                "id_card": {"file_name": "flow_test.pdf", "url": "/uploads/flow_test.pdf"},
                "national_card_front": {"file_name": "flow_test.pdf", "url": "/uploads/flow_test.pdf"},
                "national_card_back": {"file_name": "flow_test.pdf", "url": "/uploads/flow_test.pdf"},
                "education_certificate": {"file_name": "flow_test.pdf", "url": "/uploads/flow_test.pdf"},
            }
        )
    if target_state == "interview_completed":
        ctx["interview_date"] = "2026-05-01T10:00:00+00:00"
    if target_state == "course_selection":
        ctx["lms_login"] = True
    return ctx


def _semester_prep_context(process_code: str, target_state: str) -> dict[str, Any]:
    """Minimal context for semester-prep form states when using db_fallback."""
    courses = [_SAMPLE_COURSE_ROW]
    ctx: dict[str, Any] = {}
    if target_state in (
        "course_list_creation",
        "course_finalization",
        "course_list_review",
        "marketing_campaign",
        "interviewer_assignment",
        "interview_scheduling",
    ):
        ctx["courses_fall"] = courses
        ctx["courses_winter"] = courses
    if target_state in ("course_finalization", "marketing_campaign", "interviewer_assignment", "interview_scheduling"):
        ctx["courses_fall"] = [
            {**_SAMPLE_COURSE_ROW, "classroom_location": "کلاس ۱", "instructor_coordinated": True}
        ]
        ctx["courses_finalized_fall"] = ctx["courses_fall"]
    return ctx


@dataclass
class SeedResult:
    instance_id: uuid.UUID
    student_id: uuid.UUID
    student_code: str
    process_code: str
    target_state: str
    current_state: str
    mode: str  # engine_walk | known_sequence | db_fallback
    walk_steps: int = 0
    blocked_at: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)


def _bfs_path(
    process_json: dict[str, Any],
    target_state: str,
) -> list[tuple[str, str, str]] | None:
    """Shortest path as list of (from_state, trigger, to_state)."""
    proc = process_json.get("process") or {}
    initial = proc.get("initial_state")
    if not initial or initial == target_state:
        return []

    adj: dict[str, list[tuple[str, str]]] = {}
    for tr in process_json.get("transitions") or []:
        if not isinstance(tr, dict):
            continue
        frm = (tr.get("from") or "").strip()
        trigger = (tr.get("trigger") or "").strip()
        to = (tr.get("to") or "").strip()
        if frm and trigger and to:
            adj.setdefault(frm, []).append((trigger, to))

    queue: deque[str] = deque([initial])
    parent: dict[str, tuple[str, str, str] | None] = {initial: None}

    while queue:
        cur = queue.popleft()
        if cur == target_state:
            break
        for trigger, to in adj.get(cur, []):
            if to not in parent:
                parent[to] = (cur, trigger, to)
                queue.append(to)

    if target_state not in parent:
        return None

    path: list[tuple[str, str, str]] = []
    node = target_state
    while parent[node] is not None:
        frm, trigger, to = parent[node]
        path.append((frm, trigger, to))
        node = frm
    path.reverse()
    return path


async def _get_or_create_flow_student(
    db: AsyncSession,
    *,
    process_code: str,
    student_code: str,
    demo_password: str = "demo123",
) -> tuple[User, Student]:
    await ensure_demo_role_users(db)
    course_type = "comprehensive" if "comprehensive" in process_code else "introductory"
    if process_code in ("fall_semester_preparation", "winter_semester_preparation"):
        course_type = "introductory"
    return await create_demo_student(
        db,
        student_code=student_code,
        username=student_code.lower().replace("-", "_"),
        full_name_fa=f"Flow-Through {student_code}",
        password=demo_password,
        course_type=course_type,
        therapy_started=process_code in ("start_therapy", "session_payment", "attendance_tracking"),
    )


async def _get_active_instance(
    db: AsyncSession,
    student_id: uuid.UUID,
    process_code: str,
) -> ProcessInstance | None:
    stmt = (
        select(ProcessInstance)
        .where(
            ProcessInstance.student_id == student_id,
            ProcessInstance.process_code == process_code,
        )
        .order_by(ProcessInstance.started_at.desc())
    )
    rows = list((await db.execute(stmt)).scalars().all())
    active = [x for x in rows if not x.is_completed and not x.is_cancelled]
    return active[0] if active else None


async def _db_fallback(
    db: AsyncSession,
    inst: ProcessInstance,
    target_state: str,
    extra_ctx: dict[str, Any] | None = None,
) -> None:
    terminals = {
        s.get("code")
        for s in (await _load_states_for_process(inst.process_code))
        if s.get("type") == "terminal"
    }
    inst.current_state_code = target_state
    inst.is_completed = target_state in terminals
    if inst.is_completed and not inst.completed_at:
        inst.completed_at = datetime.now(timezone.utc)
    elif not inst.is_completed:
        inst.completed_at = None
    if extra_ctx:
        ctx = dict(inst.context_data or {})
        ctx.update(extra_ctx)
        inst.context_data = ctx
        flag_modified(inst, "context_data")
    await db.flush()


async def _load_states_for_process(process_code: str) -> list[dict[str, Any]]:
    from pathlib import Path
    import json

    path = Path(__file__).resolve().parents[2] / "metadata" / "processes" / f"{process_code}.json"
    if not path.is_file():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("states") or []


async def _walk_known_sequence(
    engine: StateMachineEngine,
    db: AsyncSession,
    instance_id: uuid.UUID,
    admin_id: uuid.UUID,
    sequence: list[tuple[str, str]],
    target_state: str,
) -> tuple[bool, str, int]:
    steps = 0
    for trigger, role in sequence:
        inst = await engine.get_process_instance(instance_id)
        if inst.current_state_code == target_state:
            return True, inst.current_state_code, steps
        if inst.is_completed or inst.is_cancelled:
            break
        progressed = False
        for payload in _expand_payload_variants(trigger, inst.current_state_code, inst.process_code):
            result = await engine.execute_transition(
                instance_id=instance_id,
                trigger_event=trigger,
                actor_id=admin_id,
                actor_role=role,
                payload=payload,
            )
            await db.commit()
            if result.success:
                steps += 1
                progressed = True
                break
        if not progressed:
            inst = await engine.get_process_instance(instance_id)
            return False, inst.current_state_code, steps
    inst = await engine.get_process_instance(instance_id)
    return inst.current_state_code == target_state, inst.current_state_code, steps


async def _walk_bfs_path(
    engine: StateMachineEngine,
    db: AsyncSession,
    instance_id: uuid.UUID,
    admin_id: uuid.UUID,
    path: list[tuple[str, str, str]],
    process_code: str,
) -> tuple[bool, str, int]:
    steps = 0
    merge_applied = False
    for _frm, trigger, _to in path:
        inst = await engine.get_process_instance(instance_id)
        if not merge_applied and steps >= 1:
            merge = LEVEL_C_CONTEXT_MERGE_AFTER_STEP1.get(process_code)
            if merge:
                ctx = dict(inst.context_data or {})
                ctx.update(merge)
                inst.context_data = ctx
                flag_modified(inst, "context_data")
                await db.commit()
            merge_applied = True

        progressed = False
        for payload in _expand_payload_variants(trigger, inst.current_state_code, process_code):
            result = await engine.execute_transition(
                instance_id=instance_id,
                trigger_event=trigger,
                actor_id=admin_id,
                actor_role="admin",
                payload=payload,
            )
            await db.commit()
            if result.success:
                steps += 1
                progressed = True
                break
        if not progressed:
            inst = await engine.get_process_instance(instance_id)
            return False, inst.current_state_code, steps
    inst = await engine.get_process_instance(instance_id)
    return True, inst.current_state_code, steps


async def seed_instance_at_state(
    db: AsyncSession,
    process_code: str,
    target_state: str,
    *,
    student_code: str | None = None,
    extra_ctx: dict[str, Any] | None = None,
    institute_student: bool = False,
) -> SeedResult:
    """
    Place a process instance at target_state for flow-through testing.

    Uses engine walk when possible; falls back to direct DB state mutation.
    """
    from pathlib import Path
    import json

    apply_demo_attendance_patches()
    try:
        admin = await ensure_admin_for_matrix_seed(db)
        code_suffix = (student_code or f"{FLOW_STUDENT_PREFIX}{process_code}-{target_state}")[:60]
        if institute_student or process_code in ("fall_semester_preparation", "winter_semester_preparation"):
            from app.services.institute_operational_anchor import ensure_institute_operational_student

            anchor = await ensure_institute_operational_student(db)
            student = anchor
            user = (await db.execute(select(User).where(User.id == anchor.user_id))).scalar_one()
        else:
            user, student = await _get_or_create_flow_student(
                db, process_code=process_code, student_code=code_suffix
            )

        if process_code in ("introductory_course_registration", "comprehensive_course_registration"):
            from tests.helpers.registration_gate_fixture import open_intro_registration_gate

            await open_intro_registration_gate(db)

        process_path = (
            Path(__file__).resolve().parents[2] / "metadata" / "processes" / f"{process_code}.json"
        )
        process_json = json.loads(process_path.read_text(encoding="utf-8"))
        engine = StateMachineEngine(db)

        inst = await _get_active_instance(db, student.id, process_code)
        if not inst:
            initial_ctx = dict(LEVEL_B_INITIAL_CONTEXT.get(process_code) or {})
            if extra_ctx:
                initial_ctx.update(extra_ctx)
            inst = await engine.start_process(
                process_code=process_code,
                student_id=student.id,
                actor_id=admin.id,
                actor_role="admin",
                initial_context=initial_ctx or None,
            )
            await db.commit()

        proc_initial = (process_json.get("process") or {}).get("initial_state")
        intro_reg_direct = process_code == "introductory_course_registration" and target_state != proc_initial

        if inst.current_state_code == target_state:
            mode = "already_at_target"
            walk_steps = 0
            blocked_at = None
        elif intro_reg_direct:
            intro_ctx = _intro_reg_context(target_state)
            merged_extra = {**(extra_ctx or {}), **intro_ctx}
            blocked_at = inst.current_state_code
            await _db_fallback(db, inst, target_state, merged_extra)
            if target_state in ("interview_scheduled", "interview_completed"):
                from tests.helpers.flow_through_interview_fixture import ensure_booked_slot_for_instance

                await ensure_booked_slot_for_instance(db, inst)
            await db.commit()
            inst = await engine.get_process_instance(inst.id)
            mode = "db_fallback"
            walk_steps = 0
        else:
            mode = "engine_walk"
            walk_steps = 0
            blocked_at = None
            ok = False
            final_state = inst.current_state_code

            known = KNOWN_WALK_SEQUENCES.get(process_code)
            if known:
                ok, final_state, walk_steps = await _walk_known_sequence(
                    engine, db, inst.id, admin.id, known, target_state
                )
                if ok:
                    mode = "known_sequence"

            if not ok:
                path = _bfs_path(process_json, target_state)
                if path:
                    ok, final_state, walk_steps = await _walk_bfs_path(
                        engine, db, inst.id, admin.id, path, process_code
                    )
                    mode = "engine_walk" if ok else "engine_walk_partial"

            if not ok and final_state != target_state:
                prep_ctx = _semester_prep_context(process_code, target_state)
                intro_ctx = (
                    _intro_reg_context(target_state)
                    if process_code == "introductory_course_registration"
                    else {}
                )
                merged_extra = {**(extra_ctx or {}), **prep_ctx, **intro_ctx}
                await _db_fallback(db, inst, target_state, merged_extra)
                await db.commit()
                mode = "db_fallback"
                blocked_at = final_state
                inst = await engine.get_process_instance(inst.id)

        await db.refresh(inst)
        if process_code in ("fall_semester_preparation", "winter_semester_preparation"):
            prep_ctx = _semester_prep_context(process_code, target_state)
            if prep_ctx:
                ctx = dict(inst.context_data or {})
                ctx.update(prep_ctx)
                inst.context_data = ctx
                flag_modified(inst, "context_data")
                await db.flush()
        elif process_code == "introductory_course_registration":
            intro_ctx = _intro_reg_context(target_state)
            if intro_ctx:
                ctx = dict(inst.context_data or {})
                ctx.update(intro_ctx)
                inst.context_data = ctx
                flag_modified(inst, "context_data")
                await db.flush()
        return SeedResult(
            instance_id=inst.id,
            student_id=student.id,
            student_code=getattr(student, "student_code", code_suffix),
            process_code=process_code,
            target_state=target_state,
            current_state=inst.current_state_code,
            mode=mode,
            walk_steps=walk_steps,
            blocked_at=blocked_at,
            extra={"initial_state": proc_initial, "user_id": str(user.id)},
        )
    finally:
        restore_demo_attendance_patches()
