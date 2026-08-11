"""زنجیرهٔ خودکار مراحل فرایند ۳۱ پس از ترنزیشن‌های کلیدی."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine
from app.models.operational_models import ProcessInstance, Student, User
from sqlalchemy import select

logger = logging.getLogger(__name__)

_INTRO_ADMISSION_RESULT_STATES = frozenset({
    "result_conditional_therapy",
    "result_single_course",
    "result_full_admission",
})

_INTRO_COURSE_LABEL = "دوره آشنایی کاربردی با روانکاوی معاصر"


def _ctx(instance: ProcessInstance) -> dict:
    return StateMachineEngine._as_mapping(instance.context_data)


def _set_deadlines(ctx: dict, *, hours: int = 48, payment_days: int = 14) -> dict:
    now = datetime.now(timezone.utc)
    out = dict(ctx)
    dl = (now + timedelta(hours=hours)).date().isoformat()
    pay_dl = (now + timedelta(days=payment_days)).date().isoformat()
    out.setdefault("documents_upload_deadline", dl)
    out.setdefault("registration_payment_deadline", pay_dl)
    out.setdefault("course_label", _INTRO_COURSE_LABEL)
    out.setdefault("term_label", out.get("term_label") or "ترم جاری")
    return out


async def _resolve_system_actor_id(db) -> uuid.UUID:
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row:
        return row
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row if row else uuid.uuid4()


async def _persist_admission_from_instance(db, instance: ProcessInstance, to_state: str) -> None:
    """نوع پذیرش را از context/نتیجه روی Student.extra_data بنویس (برای گیت ترم ۲)."""
    from app.services.admission_type_service import (
        persist_admission_type_on_student,
        resolve_admission_type_from_context,
    )

    ctx = _ctx(instance)
    student = (
        await db.execute(select(Student).where(Student.id == instance.student_id))
    ).scalars().first()
    if not student:
        return
    canonical = persist_admission_type_on_student(
        student,
        admission_type=ctx.get("admission_type") or resolve_admission_type_from_context(ctx),
        interview_result=ctx.get("interview_result") or ctx.get("result"),
        result_state=to_state,
    )
    if canonical and not ctx.get("admission_type"):
        ctx = dict(ctx)
        ctx["admission_type"] = canonical
        instance.context_data = ctx
        flag_modified(instance, "context_data")
    if canonical:
        logger.info(
            "persisted admission_type=%s on student=%s (intro registration)",
            canonical,
            student.id,
        )


async def chain_introductory_registration_after_transition(
    db,
    engine: StateMachineEngine,
    instance: ProcessInstance,
    to_state: str,
    actor_id: uuid.UUID,
) -> None:
    """پس از نتیجهٔ پذیرش: دعوت خودکار به بارگذاری مدارک (فقط وقتی gate باز است)."""
    if instance.process_code != "introductory_course_registration":
        return

    if to_state in _INTRO_ADMISSION_RESULT_STATES:
        await _persist_admission_from_instance(db, instance, to_state)

        from app.services.registration_readiness_service import check_intro_registration_gate

        gate = await check_intro_registration_gate(db)
        if not gate.allowed:
            ctx = _ctx(instance)
            ctx["student_next_action_fa"] = (
                "پذیرش شما ثبت شد. آپلود مدارک پس از باز شدن پنجرهٔ ثبت‌نام ترم فعال می‌شود؛ "
                "همین صفحه را بعد از اعلام باز شدن ثبت‌نام تازه کنید."
            )
            instance.context_data = ctx
            flag_modified(instance, "context_data")
            logger.info(
                "introductory proceed_to_documents deferred (gate closed) instance=%s",
                instance.id,
            )
            return

        ctx = _set_deadlines(_ctx(instance))
        instance.context_data = ctx
        flag_modified(instance, "context_data")
        await db.flush()

        sys_id = await _resolve_system_actor_id(db)
        result = await engine.execute_transition(
            instance.id,
            "proceed_to_documents",
            sys_id,
            "system",
            None,
        )
        if not result.success:
            logger.warning(
                "introductory auto proceed_to_documents failed instance=%s: %s",
                instance.id,
                result.error,
            )
