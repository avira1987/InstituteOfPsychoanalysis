"""زنجیرهٔ خودکار مراحل سیستمی فرایند ۴۱ پس از ثبت‌نام دانشجو در درس."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, Student, User

logger = logging.getLogger(__name__)

_SYSTEM_CHAIN: tuple[tuple[str, str], ...] = (
    ("links_created", "links_placed"),
    ("attendance_list_ready", "ready"),
)


async def _resolve_system_actor_id(db) -> uuid.UUID:
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row:
        return row
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row if row else uuid.uuid4()


def _selected_course_codes(instance: ProcessInstance, student: Student | None) -> list[str]:
    ctx = StateMachineEngine._as_mapping(instance.context_data)
    raw = ctx.get("selected_courses") or ctx.get("course_codes") or []
    if isinstance(raw, str):
        raw = [raw]
    codes = []
    for c in raw if isinstance(raw, (list, tuple)) else []:
        if isinstance(c, dict):
            code = c.get("code") or c.get("course_code") or c.get("value")
        else:
            code = c
        if code:
            codes.append(str(code).strip())
    if codes:
        return codes
    if not student:
        return []
    extra = student.extra_data if isinstance(student.extra_data, dict) else {}
    lms = extra.get("lms") if isinstance(extra.get("lms"), dict) else {}
    enrolled = lms.get("enrolled_courses") or []
    out = []
    for c in enrolled if isinstance(enrolled, list) else []:
        if isinstance(c, dict):
            code = c.get("code") or c.get("course_code")
        else:
            code = c
        if code:
            out.append(str(code).strip())
    return out


async def _inject_offering_prep_rows(db, instance: ProcessInstance, student: Student | None) -> None:
    """قبل از register_lesson_teaching_assistants، TA/مدرس را از TermCourseOffering در context می‌ریزد."""
    from app.services.term_course_offering_service import get_offering_by_code

    codes = _selected_course_codes(instance, student)
    if not codes:
        return
    ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
    rows = list(ctx.get("prep_course_rows") or [])
    by_code = {
        str(r.get("course_code") or r.get("value") or "").strip(): r
        for r in rows
        if isinstance(r, dict)
    }
    changed = False
    for code in codes:
        offering = await get_offering_by_code(db, code)
        if not offering:
            continue
        row = {
            "course_code": offering.course_code,
            "course_name": offering.course_name_fa,
            "teaching_assistant": offering.teaching_assistant_name or "",
            "instructor": offering.instructor_name or "",
            "day": offering.day,
            "time": offering.time_text,
        }
        by_code[code] = row
        changed = True
        if offering.course_name_fa:
            ctx.setdefault("lesson_course_label", offering.course_name_fa)
    if changed:
        ctx["prep_course_rows"] = list(by_code.values())
        instance.context_data = ctx
        flag_modified(instance, "context_data")


def _sync_lesson_dashboard_context(instance: ProcessInstance, student: Student | None) -> None:
    """فیلدهای نمایشی فرم lesson_active را از lms پروندهٔ دانشجو در context_data می‌ریزد."""
    if not student:
        return
    extra = student.extra_data if isinstance(student.extra_data, dict) else {}
    lms = extra.get("lms") if isinstance(extra.get("lms"), dict) else {}
    codes = _selected_course_codes(instance, student)
    if not codes:
        courses = lms.get("enrolled_courses") or []
        if not courses:
            return
        last = courses[-1]
        code = str(last.get("code") or last) if isinstance(last, dict) else str(last)
    else:
        code = codes[-1]
    ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
    meta = (lms.get("course_link_meta") or {}).get(code) or {}
    ctx["lesson_course_label"] = meta.get("course_name_fa") or ctx.get("lesson_course_label") or code
    links = lms.get("portal_course_links") or lms.get("course_links") or {}
    ctx["online_class_link"] = links.get(code) or links.get(str(code)) or meta.get("url") or ""
    ta_map = lms.get("teaching_assistants_by_course") or {}
    ctx["teaching_assistant_name"] = (
        ta_map.get(code) or ta_map.get(str(code)) or meta.get("teaching_assistant_name") or ""
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")


async def chain_lesson_start_after_transition(
    db,
    engine: StateMachineEngine,
    instance: ProcessInstance,
    to_state: str,
    actor_id: uuid.UUID,
) -> None:
    """پس از enrolled یا هر state میانی سیستمی، گام‌های اتوماسیون را تا lesson_active پیش ببرد."""
    if instance.process_code != "lesson_start_per_term":
        return
    if instance.is_completed or instance.is_cancelled:
        return

    sys_id = await _resolve_system_actor_id(db)
    state = to_state
    for from_state, trigger in _SYSTEM_CHAIN:
        if state != from_state:
            continue
        if from_state == "attendance_list_ready":
            st = await db.get(Student, instance.student_id)
            await _inject_offering_prep_rows(db, instance, st)
            await db.flush()
        result = await engine.execute_transition(
            instance.id,
            trigger,
            sys_id,
            "system",
            None,
        )
        if not result.success:
            logger.warning(
                "lesson_start auto %s failed instance=%s: %s",
                trigger,
                instance.id,
                result.error,
            )
            return
        instance = await engine.get_process_instance(instance.id)
        state = instance.current_state_code or result.to_state or state

    if instance.current_state_code == "lesson_active":
        st = await db.get(Student, instance.student_id)
        _sync_lesson_dashboard_context(instance, st)
        await db.flush()
