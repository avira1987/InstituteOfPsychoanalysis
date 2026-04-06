"""خلاصهٔ مسیر اصلی برای لیست ردیابی (پیشرفت تقریبی + اقدام معلق از دید دانشجو)."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.engine import InstanceNotFoundError, StateMachineEngine
from app.meta.loader import MetadataLoader
from app.meta.process_forms import get_process_forms
from app.meta.student_step_forms import filter_forms_for_student, is_state_locked_for_student
from app.models.operational_models import Student


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
) -> dict[str, Any]:
    """هم‌تراز admin-ui/src/utils/studentProcessGuidance.js — buildStudentGuidance"""
    proc = definition.get("process") or {}
    overview_fa = (str(proc.get("description") or "").strip()) if proc.get("description") else ""
    st = _find_state_definition(definition, detail.get("current_state"))
    meta = (st or {}).get("metadata") or {}
    short_fa = (str(meta.get("student_short_fa") or meta.get("student_guidance_fa") or "").strip()) or (
        (st.get("name_fa") if st else "") or detail.get("current_state") or ""
    )
    role = (st or {}).get("assigned_role")
    done = detail.get("is_completed") or detail.get("is_cancelled")

    student_forms = filter_forms_for_student(forms or [])
    n_trans = len(transitions or [])
    has_forms = len(student_forms) > 0
    has_student_work = n_trans > 0 or has_forms

    task_fa = ""
    if not done and st:
        custom_task = str(meta.get("student_task_fa") or "").strip()
        if custom_task:
            task_fa = custom_task
        elif role == "student" and has_student_work:
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
        elif role == "student" and not has_student_work:
            task_fa = (
                "در این لحظه کاری از داخل پنل برای شما پیش‌بینی نشده؛ اگر پیامی دریافت کردید طبق آن عمل کنید؛ "
                "در غیر این صورت بعداً همین صفحه را تازه کنید."
            )
        elif role and role != "student":
            task_fa = (
                "در این مرحله اقدام مستقیم از پنل شما لازم نیست؛ منتظر بررسی یا اقدام همکاران بمانید و "
                "بعداً همین صفحه را تازه کنید."
            )
        else:
            task_fa = "در این مرحله اقدام مستقیم از پنل شما لازم نیست؛ منتظر پیگیری بمانید."

    return {
        "overview_fa": overview_fa,
        "short_fa": short_fa,
        "task_fa": task_fa or "",
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
