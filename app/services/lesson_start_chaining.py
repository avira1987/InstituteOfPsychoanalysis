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


def _sync_lesson_dashboard_context(instance: ProcessInstance, student: Student | None) -> None:
    """فیلدهای نمایشی فرم lesson_active را از lms پروندهٔ دانشجو در context_data می‌ریزد."""
    if not student:
        return
    extra = student.extra_data if isinstance(student.extra_data, dict) else {}
    lms = extra.get("lms") if isinstance(extra.get("lms"), dict) else {}
    courses = lms.get("enrolled_courses") or []
    if not courses:
        return
    code = str(courses[-1])
    ctx = dict(StateMachineEngine._as_mapping(instance.context_data))
    ctx["lesson_course_label"] = code
    links = lms.get("portal_course_links") or lms.get("course_links") or {}
    ctx["online_class_link"] = links.get(code) or links.get(str(code)) or ""
    ta_map = lms.get("teaching_assistants_by_course") or {}
    ctx["teaching_assistant_name"] = ta_map.get(code) or ta_map.get(str(code)) or ""
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
