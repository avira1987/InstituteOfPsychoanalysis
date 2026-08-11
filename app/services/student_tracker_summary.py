"""خلاصهٔ مسیر اصلی برای لیست ردیابی (پیشرفت تقریبی + اقدام معلق از دید دانشجو)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional
from urllib.parse import urlencode

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.engine import InstanceNotFoundError, StateMachineEngine
from app.meta.loader import MetadataLoader
from app.meta.process_forms import get_process_forms
from app.meta.student_step_forms import filter_forms_for_student, is_state_locked_for_student
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import ProcessInstance, Student

INBOX_ITEM_CAP = 20


def _find_state_definition(definition: dict, state_code: Optional[str]) -> Optional[dict]:
    if not definition or not state_code:
        return None
    for s in definition.get("states") or []:
        if s.get("code") == state_code:
            return s
    return None


def build_roadmap_states(definition: dict) -> list[dict]:
    """هم‌تراز admin-ui/src/utils/studentRoadmap.js — buildRoadmapStates"""
    if not definition or not definition.get("states"):
        return []
    initial = (definition.get("process") or {}).get("initial_state")
    states = definition["states"]
    trans = definition.get("transitions") or []
    code_set = {s["code"] for s in states if s.get("code")}
    adj: dict[str, list[str]] = {}
    for t in trans:
        f, to = t.get("from"), t.get("to")
        if not f or not to or f not in code_set or to not in code_set:
            continue
        adj.setdefault(f, []).append(to)
    visited: list[str] = []
    seen: set[str] = set()

    def walk(code: str) -> None:
        if code in seen:
            return
        seen.add(code)
        visited.append(code)
        for n in adj.get(code, []):
            walk(n)

    if initial:
        walk(initial)
    for s in states:
        c = s.get("code")
        if c and c not in seen:
            visited.append(c)
    by_code = {s["code"]: s for s in states if s.get("code")}
    return [by_code[c] for c in visited if c in by_code]


def graduation_progress_pct(definition: dict, current_state: Optional[str], is_completed: bool) -> int:
    """درصد پیشرفت تقریبی مسیر (مثل کارت «مسیر این فرایند» در پنل دانشجو)."""
    if is_completed:
        return 100
    roadmap = build_roadmap_states(definition)
    if not roadmap or not current_state:
        return 0
    codes = [s["code"] for s in roadmap]
    try:
        idx = codes.index(current_state)
    except ValueError:
        return 0
    return min(100, round((idx + 1) / len(codes) * 100))


def build_student_guidance(
    definition: dict,
    detail: dict[str, Any],
    transitions: list[dict[str, Any]],
    forms: list,
    step_form_locked: bool,
    registration_gate: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """هم‌تراز admin-ui/src/utils/studentProcessGuidance.js — buildStudentGuidance"""
    proc = definition.get("process") or {}
    proc_code = proc.get("code")
    overview_fa = (str(proc.get("description") or "").strip()) if proc.get("description") else ""
    st = _find_state_definition(definition, detail.get("current_state"))
    meta = (st or {}).get("metadata") or {}
    ctx = StateMachineEngine._as_mapping(detail.get("context_data"))
    short_fa = (str(meta.get("student_short_fa") or meta.get("student_guidance_fa") or "").strip()) or (
        (st.get("name_fa") if st else "") or detail.get("current_state") or ""
    )
    why_fa = str(meta.get("student_why_fa") or "").strip()
    role = (st or {}).get("assigned_role")
    done = detail.get("is_completed") or detail.get("is_cancelled")

    student_forms = filter_forms_for_student(forms or [])
    n_trans = len(transitions or [])
    has_forms = len(student_forms) > 0
    has_student_work = n_trans > 0 or has_forms
    student_or_applicant = role in ("student", "applicant")

    task_fa = ""
    if not done and st:
        custom_task = str(meta.get("student_task_fa") or "").strip()
        if custom_task:
            task_fa = custom_task
        elif student_or_applicant and has_student_work:
            if has_forms and not step_form_locked:
                task_fa = (
                    "فرم‌های همین صفحه را تکمیل و ثبت کنید؛ بعد از ثبت، اگر دکمهٔ اقدام بعدی "
                    "برای شما فعال بود همان را بزنید."
                )
            elif n_trans > 0:
                labels: list[str] = []
                for t in transitions or []:
                    lab = t.get("description_fa") or t.get("description") or t.get("trigger_event")
                    if lab:
                        labels.append(str(lab))
                if len(labels) == 1:
                    task_fa = f"اقدام لازم از سمت شما: {labels[0]}"
                else:
                    task_fa = "یکی از اقدام‌های زیر را انجام دهید: " + "؛ ".join(labels)
            elif has_forms and step_form_locked:
                task_fa = (
                    "اطلاعات این مرحله قبلاً ثبت شده است؛ اگر دکمهٔ مرحلهٔ بعد را می‌بینید همان را بزنید؛ "
                    "در غیر این صورت منتظر اقدام اداری بمانید."
                )
        elif student_or_applicant and not has_student_work:
            task_fa = (
                "در این لحظه کاری از داخل پنل برای شما پیش‌بینی نشده؛ اگر پیامی دریافت کردید طبق آن عمل کنید؛ "
                "در غیر این صورت بعداً همین صفحه را تازه کنید."
            )
        elif role and role not in ("student", "applicant"):
            task_fa = (
                "در این مرحله اقدام مستقیم از پنل شما لازم نیست؛ منتظر بررسی یا اقدام همکاران بمانید و "
                "بعداً همین صفحه را تازه کنید."
            )
        else:
            task_fa = "در این مرحله اقدام مستقیم از پنل شما لازم نیست؛ منتظر پیگیری بمانید."

    ctx_override = str(ctx.get("student_next_action_fa") or "").strip()
    if not done and ctx_override:
        task_fa = ctx_override

    intro_gate_closed = (
        proc_code == "introductory_course_registration"
        and registration_gate is not None
        and registration_gate.get("allowed") is False
    )
    admission_results = frozenset({
        "result_conditional_therapy",
        "result_single_course",
        "result_full_admission",
    })
    if (
        not done
        and intro_gate_closed
        and detail.get("current_state") in admission_results
    ):
        task_fa = str(registration_gate.get("reason_fa") or "").strip() or (
            "پذیرش شما ثبت شد. آپلود مدارک پس از باز شدن پنجرهٔ ثبت‌نام ترم فعال می‌شود؛ "
            "همین صفحه را بعد از اعلام باز شدن ثبت‌نام تازه کنید."
        )

    return {
        "overview_fa": overview_fa,
        "short_fa": short_fa,
        "task_fa": task_fa or "",
        "why_fa": why_fa,
        "role": role,
        "done": done,
    }


async def summarize_primary_path_for_student(db: AsyncSession, student: Student) -> dict[str, Any]:
    """
    پیشرفت تقریبی مسیر اصلی و متن اقدام معلق از دید نقش student (برای نمایش به ادمین).
    """
    # JSONB گاهی به‌صورت رشتهٔ JSON (دادهٔ قدیمی/اسکریپت) برمی‌گردد؛ .get روی str خطای ۵۰۰ می‌دهد.
    extra = StateMachineEngine._as_mapping(student.extra_data)
    pid = extra.get("primary_instance_id")
    empty = {
        "graduation_progress_pct": None,
        "pending_action_fa": "مسیر اصلی فرایند ثبت نشده است.",
        "primary_process_name_fa": None,
        "primary_current_state": None,
        "primary_path_missing": True,
    }
    if not pid:
        return empty
    try:
        iid = uuid.UUID(str(pid))
    except (ValueError, TypeError):
        return empty

    engine = StateMachineEngine(db)
    try:
        status = await engine.get_instance_status(iid)
    except InstanceNotFoundError:
        return empty

    loader = MetadataLoader(db)
    definition = await loader.load_process(status["process_code"])
    if not definition:
        return {
            "graduation_progress_pct": None,
            "pending_action_fa": "تعریف فرایند یافت نشد.",
            "primary_process_name_fa": status["process_code"],
            "primary_current_state": status.get("current_state"),
            "primary_path_missing": False,
        }

    transitions = await engine.get_available_transitions(iid, "student")
    forms = get_process_forms(status["process_code"], state_code=status.get("current_state"))
    step_locked = is_state_locked_for_student(status.get("context_data"), status.get("current_state"))
    guidance = build_student_guidance(definition, status, transitions, forms, step_locked)

    pct = graduation_progress_pct(definition, status.get("current_state"), bool(status.get("is_completed")))

    if status.get("is_completed"):
        pending = "مسیر اصلی (فرایند جاری) تکمیل شده است."
    elif status.get("is_cancelled"):
        pending = "فرایند اصلی لغو شده است."
    else:
        pending = (guidance.get("task_fa") or "").strip() or (guidance.get("short_fa") or "").strip()

    pname = (definition.get("process") or {}).get("name_fa") or status["process_code"]

    return {
        "graduation_progress_pct": pct,
        "pending_action_fa": pending or None,
        "primary_process_name_fa": pname,
        "primary_current_state": status.get("current_state"),
        "primary_path_missing": False,
    }


def _student_action_inbox_path(instance_id: uuid.UUID | str) -> str:
    q = urlencode({"tab": "processes", "instance_id": str(instance_id)})
    return f"/panel/portal/student?{q}"


def _student_action_hint_path() -> str:
    return "/panel/portal/student?tab=sessions"


async def build_student_action_inbox(db: AsyncSession, student: Student) -> dict[str, Any]:
    """
    فهرست اقدام‌های قابل‌انجام دانشجو روی instanceهای فعال (نقش student/applicant).
    هم‌تراز صندوق اقدام داشبورد — با short/task/why از build_student_guidance.
    """
    from app.services.semester_prep_service import PREP_PROCESS_CODES

    extra = StateMachineEngine._as_mapping(student.extra_data)
    primary_raw = extra.get("primary_instance_id")
    primary_id = str(primary_raw).strip() if primary_raw else None

    intro_gate: Optional[dict[str, Any]] = None
    if student.course_type == "introductory":
        from app.services.registration_readiness_service import check_intro_registration_gate

        intro_gate = (await check_intro_registration_gate(db)).to_dict()

    pd = aliased(ProcessDefinition)
    sd = aliased(StateDefinition)
    stmt = (
        select(ProcessInstance, pd, sd)
        .join(pd, ProcessInstance.process_code == pd.code)
        .outerjoin(
            sd,
            (sd.process_id == pd.id) & (sd.code == ProcessInstance.current_state_code),
        )
        .where(
            ProcessInstance.student_id == student.id,
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
        )
        .order_by(desc(ProcessInstance.last_transition_at), desc(ProcessInstance.started_at))
        .limit(200)
    )
    res = await db.execute(stmt)
    sources: list[tuple[ProcessInstance, ProcessDefinition, StateDefinition]] = []
    for pi, proc_def, state_def in res.all():
        if pi.process_code in PREP_PROCESS_CODES:
            continue
        if state_def is None:
            continue
        ar = (state_def.assigned_role or "").strip().lower()
        if ar not in ("student", "applicant"):
            continue
        sources.append((pi, proc_def, state_def))

    def _sort_key(row: tuple[ProcessInstance, ProcessDefinition, StateDefinition]) -> tuple:
        pi = row[0]
        is_primary = primary_id and str(pi.id) == primary_id
        sort_at = pi.last_transition_at or pi.started_at
        return (
            0 if is_primary else 1,
            sort_at is None,
            sort_at or datetime.min,
        )

    sources.sort(key=_sort_key)

    engine = StateMachineEngine(db)
    loader = MetadataLoader(db)
    items: list[dict[str, Any]] = []

    for pi, proc_def, _state_def in sources[:INBOX_ITEM_CAP]:
        try:
            status = await engine.get_instance_status(pi.id)
        except InstanceNotFoundError:
            continue

        definition = await loader.load_process(status["process_code"])
        if not definition:
            continue

        transitions = await engine.get_available_transitions(pi.id, "student")
        forms = get_process_forms(status["process_code"], state_code=status.get("current_state"))
        step_locked = is_state_locked_for_student(
            status.get("context_data"),
            status.get("current_state"),
        )
        reg_gate = (
            intro_gate
            if status["process_code"] == "introductory_course_registration"
            else None
        )
        guidance = build_student_guidance(
            definition,
            status,
            transitions,
            forms,
            step_locked,
            reg_gate,
        )
        pname = (proc_def.name_fa or status["process_code"]).strip()
        iid = str(pi.id)
        items.append(
            {
                "kind": "process",
                "instance_id": iid,
                "process_code": status["process_code"],
                "process_name_fa": pname,
                "current_state": status.get("current_state"),
                "is_primary": bool(primary_id and iid == primary_id),
                "short_fa": (guidance.get("short_fa") or "").strip(),
                "task_fa": (guidance.get("task_fa") or "").strip(),
                "why_fa": (guidance.get("why_fa") or "").strip(),
                "action_path": _student_action_inbox_path(pi.id),
            }
        )

    if not items:
        hint = str(extra.get("dashboard_therapy_hint_fa") or "").strip()
        if hint:
            items.append(
                {
                    "kind": "hint",
                    "instance_id": None,
                    "process_code": None,
                    "process_name_fa": None,
                    "current_state": None,
                    "is_primary": False,
                    "short_fa": "راهنمای مسیر درمان",
                    "task_fa": hint,
                    "why_fa": "",
                    "action_path": _student_action_hint_path(),
                }
            )

    return {"items": items, "total": len(items)}
