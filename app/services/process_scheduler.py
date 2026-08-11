"""موتور زمان‌بندی فرایند — تکمیل اتوماسیون فرایندهای دسته ۳.

فراخوانی از ``calendar_triggers.run_calendar_trigger_pass`` در هر دور پس‌زمینه.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.engine import StateMachineEngine, InvalidTransitionError
from app.models.meta_models import ProcessDefinition, StateDefinition, TransitionDefinition
from app.models.operational_models import ProcessInstance, Student, User
from app.services.institute_calendar_service import get_active_calendar, resolve_registration_window
from app.services.notification_service import notification_service
from app.services.process_service import ProcessService
from app.services.sms_gateway import normalize_ir_mobile
from app.utils.date_utils import get_current_term_week

logger = logging.getLogger(__name__)

SYSTEM_ACTOR_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")

INSTALLMENT_PROCESS_CODES = (
    "intro_second_semester_registration",
    "introductory_course_registration",
    "comprehensive_course_registration",
    "comprehensive_term_start",
)

GENERIC_SLA_TRIGGERS = frozenset({"sla_breach", "deadline_passed", "sla_expired"})

INTERN_MILESTONE_MONTHS = (4, 7, 12, 16, 20, 24, 28)

TA_CONSULTATION_SESSIONS = (5, 10, 15)


def _context_as_dict(instance: ProcessInstance) -> dict[str, Any]:
    return StateMachineEngine._as_mapping(instance.context_data)


def _student_extra(student: Student) -> dict[str, Any]:
    return StateMachineEngine._as_mapping(student.extra_data)


def _parse_iso_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str):
        try:
            s = value.replace("Z", "+00:00")
            d = datetime.fromisoformat(s)
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            return d
        except Exception:
            return None
    return None


def _parse_date(value: Any) -> Optional[date]:
    from app.utils.shamsi_calendar_utils import tehran_calendar_date

    return tehran_calendar_date(value)


async def _resolve_system_actor(db: AsyncSession) -> uuid.UUID:
    row = (await db.execute(select(User.id).where(User.role == "admin").limit(1))).scalars().first()
    if row:
        return row
    row = (await db.execute(select(User.id).limit(1))).scalars().first()
    return row or SYSTEM_ACTOR_ID


async def _has_active_instance(
    db: AsyncSession,
    student_id: uuid.UUID,
    process_code: str,
) -> bool:
    stmt = select(func.count(ProcessInstance.id)).where(
        ProcessInstance.student_id == student_id,
        ProcessInstance.process_code == process_code,
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
    )
    return int((await db.execute(stmt)).scalar() or 0) > 0


async def _start_process_if_absent(
    db: AsyncSession,
    *,
    student_id: uuid.UUID,
    process_code: str,
    initial_context: Optional[dict] = None,
    fingerprint_key: str,
    fingerprint_val: str,
) -> Optional[dict]:
    extra_stmt = select(Student).where(Student.id == student_id)
    st = (await db.execute(extra_stmt)).scalars().first()
    if not st:
        return None
    extra = _student_extra(st)
    fps = extra.get("scheduler_fingerprints") or {}
    if fps.get(fingerprint_key) == fingerprint_val:
        return None
    if await _has_active_instance(db, student_id, process_code):
        fps[fingerprint_key] = fingerprint_val
        extra["scheduler_fingerprints"] = fps
        st.extra_data = extra
        flag_modified(st, "extra_data")
        return None
    actor_id = await _resolve_system_actor(db)
    svc = ProcessService(db)
    try:
        inst = await svc.start_process_for_student(
            process_code=process_code,
            student_id=student_id,
            actor_id=actor_id,
            actor_role="system",
            initial_context=initial_context or {"source": "process_scheduler"},
        )
    except Exception as e:
        logger.warning("scheduler start_process failed %s student=%s: %s", process_code, student_id, e)
        return None
    fps[fingerprint_key] = fingerprint_val
    extra["scheduler_fingerprints"] = fps
    st.extra_data = extra
    flag_modified(st, "extra_data")
    return {"student_id": str(student_id), "instance_id": str(inst.id), "process_code": process_code}


async def dispatch_scheduled_reminders(db: AsyncSession, now: datetime) -> list[dict]:
    """اجرای ``student.extra_data.scheduled_reminders`` با ``due_at <= now``."""
    out: list[dict] = []
    stmt = select(Student).where(Student.is_sample_data.is_(False))
    students = list((await db.execute(stmt)).scalars().all())
    engine = StateMachineEngine(db)

    for st in students:
        extra = _student_extra(st)
        items = list(extra.get("scheduled_reminders") or [])
        if not items:
            continue
        changed = False
        user = await db.get(User, st.user_id) if st.user_id else None
        phone = normalize_ir_mobile(user.phone or "") if user else ""

        for rec in items:
            if rec.get("sent"):
                continue
            due = _parse_iso_datetime(rec.get("due_at"))
            if due is None or now < due:
                continue
            tpl = rec.get("template") or "process_reminder"
            trigger = rec.get("trigger_event")
            inst_id_raw = rec.get("instance_id")
            if phone and len(phone) >= 10:
                sms_ctx = {"student_name": (user.full_name_fa or "").strip() if user else ""}
                if rec.get("type") == "installment":
                    amount_rial = rec.get("amount_rial")
                    if amount_rial is not None:
                        sms_ctx["amount"] = int(amount_rial)
                        sms_ctx["amount_rial"] = int(amount_rial)
                        sms_ctx["amount_toman"] = int(amount_rial) // 10
                    due_raw = rec.get("installment_due_at")
                    if due_raw:
                        # Pass full value — normalize_sms_context_dates converts via Tehran calendar.
                        # Do NOT slice [:10] (UTC date prefix can be one day early vs Tehran).
                        sms_ctx["due_date"] = due_raw
                        # #region agent log
                        try:
                            import json as _json
                            from pathlib import Path as _Path
                            from time import time as _time
                            from app.utils.shamsi_calendar_utils import (
                                format_shamsi_date as _fsd,
                                tehran_today as _tt,
                            )
                            _line = {
                                "sessionId": "8e31fd",
                                "hypothesisId": "A,B",
                                "location": "process_scheduler.py:dispatch_scheduled_reminders",
                                "message": "installment due_date for sms (no utc slice)",
                                "data": {
                                    "due_raw": str(due_raw)[:80],
                                    "due_date_shamsi": _fsd(due_raw),
                                    "sliced_would_have_been": str(due_raw)[:10],
                                    "remind_due_at": str(rec.get("due_at"))[:80],
                                    "now": now.isoformat() if hasattr(now, "isoformat") else str(now),
                                    "utc_today": str(now.date()) if hasattr(now, "date") else None,
                                    "tehran_today": str(_tt()),
                                    "template": tpl,
                                },
                                "timestamp": int(_time() * 1000),
                                "runId": "post-fix",
                            }
                            with open(
                                _Path(__file__).resolve().parents[2] / "debug-8e31fd.log",
                                "a",
                                encoding="utf-8",
                            ) as _f:
                                _f.write(_json.dumps(_line, ensure_ascii=False) + "\n")
                        except Exception:
                            pass
                        # #endregion
                    seq = rec.get("sequence")
                    if seq is not None:
                        sms_ctx["installment_index"] = seq
                try:
                    await notification_service.send_notification(
                        "sms",
                        tpl,
                        phone,
                        sms_ctx,
                    )
                except Exception as e:
                    logger.warning("scheduled_reminder sms failed student=%s: %s", st.id, e)
            if trigger and inst_id_raw:
                try:
                    iid = uuid.UUID(str(inst_id_raw))
                    r = await engine.execute_transition(
                        instance_id=iid,
                        trigger_event=str(trigger),
                        actor_id=SYSTEM_ACTOR_ID,
                        actor_role="system",
                    )
                    if r.success:
                        out.append({"student_id": str(st.id), "trigger": trigger, "reminder_id": rec.get("id")})
                except Exception as e:
                    logger.debug("scheduled_reminder transition skipped: %s", e)
            rec["sent"] = True
            rec["sent_at"] = now.isoformat()
            changed = True
            out.append({"student_id": str(st.id), "template": tpl, "reminder_id": rec.get("id")})

        if changed:
            extra["scheduled_reminders"] = items
            st.extra_data = extra
            flag_modified(st, "extra_data")

    return out


async def dispatch_installment_overdue(db: AsyncSession, today: date) -> list[dict]:
    """سررسید قسط: ``registration_complete`` + ``next_installment_due_at`` ≤ امروز."""
    out: list[dict] = []
    engine = StateMachineEngine(db)
    for pcode in INSTALLMENT_PROCESS_CODES:
        stmt = select(ProcessInstance).where(
            ProcessInstance.process_code == pcode,
            ProcessInstance.current_state_code == "registration_complete",
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
        )
        for instance in (await db.execute(stmt)).scalars().all():
            ctx = _context_as_dict(instance)
            try:
                pend = int(ctx.get("pending_installments_remaining") or 0)
            except (TypeError, ValueError):
                pend = 0
            if pend <= 0:
                continue
            due_d = _parse_date(ctx.get("next_installment_due_at"))
            if not due_d or due_d > today:
                continue
            fp = ctx.get("scheduler_fingerprint_installment_overdue")
            if fp == due_d.isoformat():
                continue
            try:
                r = await engine.execute_transition(
                    instance_id=instance.id,
                    trigger_event="installment_due_date_passed",
                    actor_id=SYSTEM_ACTOR_ID,
                    actor_role="system",
                )
                if r.success:
                    ctx["scheduler_fingerprint_installment_overdue"] = due_d.isoformat()
                    instance.context_data = ctx
                    flag_modified(instance, "context_data")
                    out.append(
                        {
                            "instance_id": str(instance.id),
                            "process_code": pcode,
                            "trigger": "installment_due_date_passed",
                        }
                    )
            except (InvalidTransitionError, Exception) as e:
                logger.warning("installment_due_date_passed failed instance=%s: %s", instance.id, e)
    return out


async def dispatch_generic_sla_triggers(db: AsyncSession, now: datetime) -> list[dict]:
    """ترنزیشن system با trigger ``sla_breach`` / ``deadline_passed`` / ``sla_expired`` پس از گذشت SLA."""
    out: list[dict] = []
    engine = StateMachineEngine(db)
    stmt = (
        select(ProcessInstance, ProcessDefinition, StateDefinition)
        .select_from(ProcessInstance)
        .join(
            ProcessDefinition,
            (ProcessDefinition.code == ProcessInstance.process_code)
            & (ProcessDefinition.is_active.is_(True)),
        )
        .join(
            StateDefinition,
            (StateDefinition.process_id == ProcessDefinition.id)
            & (StateDefinition.code == ProcessInstance.current_state_code),
        )
        .where(
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
            StateDefinition.sla_hours.isnot(None),
        )
    )
    for instance, pd, sd in (await db.execute(stmt)).all():
        if not sd.sla_hours:
            continue
        lt = instance.last_transition_at
        if lt is None:
            continue
        if lt.tzinfo is None:
            lt = lt.replace(tzinfo=timezone.utc)
        elapsed_h = (now - lt).total_seconds() / 3600.0
        if elapsed_h <= float(sd.sla_hours):
            continue

        ctx = _context_as_dict(instance)
        fired = list(ctx.get("__sla_fired_triggers") or [])

        if instance.process_code.endswith("_course_completion") or instance.process_code.endswith(
            "_attendance_completion"
        ):
            ctx.setdefault("grades_submitted_before_sla", False)
            instance.context_data = ctx
            flag_modified(instance, "context_data")

        t_stmt = select(TransitionDefinition).where(
            TransitionDefinition.process_id == pd.id,
            TransitionDefinition.from_state_code == instance.current_state_code,
            TransitionDefinition.trigger_event.in_(tuple(GENERIC_SLA_TRIGGERS)),
        )
        transitions = list((await db.execute(t_stmt)).scalars().all())
        for tr in transitions:
            te = tr.trigger_event
            if te in fired:
                continue
            try:
                r = await engine.execute_transition(
                    instance_id=instance.id,
                    trigger_event=te,
                    actor_id=SYSTEM_ACTOR_ID,
                    actor_role="system",
                )
                if r.success:
                    fired.append(te)
                    ctx["__sla_fired_triggers"] = fired
                    instance.context_data = ctx
                    flag_modified(instance, "context_data")
                    out.append(
                        {
                            "instance_id": str(instance.id),
                            "process_code": instance.process_code,
                            "trigger": te,
                        }
                    )
                    break
            except (InvalidTransitionError, Exception) as e:
                logger.debug("generic_sla trigger=%s instance=%s: %s", te, instance.id, e)
    return out


def _grades_all_entered(extra: dict[str, Any]) -> bool:
    lms = extra.get("lms") or {}
    if lms.get("all_term_grades_entered") is True:
        return True
    pending = lms.get("grades_pending")
    if pending is not None:
        try:
            return int(pending) <= 0
        except (TypeError, ValueError):
            pass
    return False


async def dispatch_academic_term_batch(db: AsyncSession, now: datetime) -> list[dict]:
    """تریگرهای تقویم ترم: ثبت‌نام، ارزیابی، پایان/آغاز ترم."""
    out: list[dict] = []
    cal = await get_active_calendar(db)
    if not cal:
        return out

    engine = StateMachineEngine(db)
    today = now.date()
    fp_term = cal.term_code or "default"

    stmt = select(Student).where(Student.is_sample_data.is_(False))
    students = list((await db.execute(stmt)).scalars().all())

    # student_instructor_evaluation — باز کردن و بستن
    if cal.evaluation_open_at and now >= cal.evaluation_open_at:
        for st in students:
            hit = await _start_process_if_absent(
                db,
                student_id=st.id,
                process_code="student_instructor_evaluation",
                initial_context={"term_code": fp_term},
                fingerprint_key=f"eval_open:{fp_term}",
                fingerprint_val=cal.evaluation_open_at.isoformat(),
            )
            if hit:
                out.append({**hit, "trigger": "evaluation_open"})

    if cal.evaluation_close_at and now >= cal.evaluation_close_at:
        ev_stmt = select(ProcessInstance).where(
            ProcessInstance.process_code == "student_instructor_evaluation",
            ProcessInstance.current_state_code == "evaluation_open",
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
        )
        for inst in (await db.execute(ev_stmt)).scalars().all():
            try:
                r = await engine.execute_transition(
                    instance_id=inst.id,
                    trigger_event="deadline_reached",
                    actor_id=SYSTEM_ACTOR_ID,
                    actor_role="system",
                )
                if r.success:
                    out.append({"instance_id": str(inst.id), "trigger": "deadline_reached"})
            except Exception as e:
                logger.debug("evaluation deadline_reached: %s", e)

    # comprehensive_term_start — پنجره ثبت‌نام
    reg_open, reg_deadline = resolve_registration_window(cal)
    in_reg_window = (
        (reg_open is None or now >= reg_open)
        and (reg_deadline is None or now <= reg_deadline)
    )
    if in_reg_window:
        for st in students:
            if st.course_type != "comprehensive":
                continue
            hit = await _start_process_if_absent(
                db,
                student_id=st.id,
                process_code="comprehensive_term_start",
                initial_context={"term_code": fp_term},
                fingerprint_key=f"comp_term_start:{fp_term}",
                fingerprint_val=fp_term,
            )
            if hit:
                out.append({**hit, "trigger": "term_registration_window"})

    # student_non_registration — پس از مهلت ثبت‌نام
    if reg_deadline and now > reg_deadline:
        for st in students:
            if st.course_type not in ("introductory", "comprehensive"):
                continue
            if await _has_active_instance(db, st.id, "comprehensive_term_start"):
                continue
            if await _has_active_instance(db, st.id, "lesson_start_per_term"):
                continue
            extra = _student_extra(st)
            lms = extra.get("lms") or {}
            if lms.get("term_registered") is True:
                continue
            hit = await _start_process_if_absent(
                db,
                student_id=st.id,
                process_code="student_non_registration",
                initial_context={"term_code": fp_term, "source": "registration_deadline_passed"},
                fingerprint_key=f"non_registration:{fp_term}",
                fingerprint_val=fp_term,
            )
            if hit:
                out.append({**hit, "trigger": "registration_deadline_passed"})

        # term end watchers — all grades entered
    for st in students:
        extra = _student_extra(st)
        if not _grades_all_entered(extra):
            continue
        pcode = "comprehensive_term_end" if st.course_type == "comprehensive" else "introductory_term_end"
        trigger = "all_grades_entered" if pcode == "comprehensive_term_end" else "all_instructor_grades_entered"
        hit = await _start_process_if_absent(
            db,
            student_id=st.id,
            process_code=pcode,
            initial_context={"term_code": fp_term},
            fingerprint_key=f"term_end:{fp_term}:{pcode}",
            fingerprint_val=fp_term,
        )
        if hit:
            try:
                if pcode == "introductory_term_end":
                    from app.services.introductory_term_end_chaining import advance_introductory_term_end

                    inst = await engine.get_process_instance(uuid.UUID(hit["instance_id"]))
                    if inst:
                        steps = await advance_introductory_term_end(
                            db, engine, inst, SYSTEM_ACTOR_ID
                        )
                        hit = {**hit, "advanced": steps}
                else:
                    await engine.execute_transition(
                        instance_id=uuid.UUID(hit["instance_id"]),
                        trigger_event=trigger,
                        actor_id=SYSTEM_ACTOR_ID,
                        actor_role="system",
                    )
            except Exception:
                pass
            out.append({**hit, "trigger": trigger})

    # lesson_start_per_term — اول ترم برای enrolled courses (str یا dict)
    if cal.term_start_date and today >= cal.term_start_date:
        for st in students:
            extra = _student_extra(st)
            lms = extra.get("lms") or {}
            courses = lms.get("enrolled_courses") or []
            if not isinstance(courses, list) or not courses:
                # course_links may be a dict {code: url} — use keys
                links = lms.get("course_links") or {}
                if isinstance(links, dict):
                    courses = list(links.keys())
                elif isinstance(links, list):
                    courses = links
            if not isinstance(courses, list):
                continue
            for course in courses:
                if isinstance(course, dict):
                    course_code = course.get("code") or course.get("course_code") or course.get("id")
                elif isinstance(course, str):
                    course_code = course.strip()
                else:
                    continue
                if not course_code:
                    continue
                course_code = str(course_code)
                fp_key = f"lesson_start:{fp_term}:{course_code}"
                fps = extra.get("scheduler_fingerprints") or {}
                if fps.get(fp_key) == fp_term:
                    continue
                if await _has_active_instance(db, st.id, "lesson_start_per_term"):
                    continue
                hit = await _start_process_if_absent(
                    db,
                    student_id=st.id,
                    process_code="lesson_start_per_term",
                    initial_context={
                        "course_code": course_code,
                        "selected_courses": [course_code],
                        "term_code": fp_term,
                    },
                    fingerprint_key=fp_key,
                    fingerprint_val=fp_term,
                )
                if hit:
                    fps[fp_key] = fp_term
                    extra["scheduler_fingerprints"] = fps
                    st.extra_data = extra
                    flag_modified(st, "extra_data")
                    out.append({**hit, "trigger": "term_start_lesson"})

    return out


def _intern_months_since(start: date, today: date) -> int:
    return max(0, (today.year - start.year) * 12 + today.month - start.month)


async def dispatch_student_milestones(db: AsyncSession, today: date) -> list[dict]:
    """milestone انترn، TA auto-upgrade، week9 در start_therapy."""
    out: list[dict] = []
    engine = StateMachineEngine(db)
    stmt = select(Student).where(Student.is_sample_data.is_(False))
    students = list((await db.execute(stmt)).scalars().all())

    for st in students:
        extra = _student_extra(st)

        # intern_hours_increase
        intern_start = _parse_date(extra.get("intern_start_date"))
        if intern_start and st.is_intern:
            months = _intern_months_since(intern_start, today)
            if months in INTERN_MILESTONE_MONTHS:
                fp = f"intern_hours:{months}"
                hit = await _start_process_if_absent(
                    db,
                    student_id=st.id,
                    process_code="intern_hours_increase",
                    initial_context={"intern_month": months},
                    fingerprint_key=fp,
                    fingerprint_val=str(today.isoformat()),
                )
                if hit:
                    try:
                        await engine.execute_transition(
                            instance_id=uuid.UUID(hit["instance_id"]),
                            trigger_event="intern_month_milestone_reached",
                            actor_id=SYSTEM_ACTOR_ID,
                            actor_role="system",
                        )
                    except Exception:
                        pass
                    out.append({**hit, "trigger": "intern_month_milestone_reached", "month": months})

        # internship_12month_conditional_review
        cond_start = _parse_date(extra.get("conditional_intern_start") or extra.get("intern_start_date"))
        if cond_start and st.is_intern and extra.get("conditional_intern") is True:
            months = _intern_months_since(cond_start, today)
            if months >= 12:
                hit = await _start_process_if_absent(
                    db,
                    student_id=st.id,
                    process_code="internship_12month_conditional_review",
                    initial_context={"intern_month": months},
                    fingerprint_key="intern_12month_review",
                    fingerprint_val=str(today.isoformat())[:7],
                )
                if hit:
                    try:
                        await engine.execute_transition(
                            instance_id=uuid.UUID(hit["instance_id"]),
                            trigger_event="conditional_intern_enters_month_12",
                            actor_id=SYSTEM_ACTOR_ID,
                            actor_role="system",
                        )
                    except Exception:
                        pass
                    out.append({**hit, "trigger": "conditional_intern_enters_month_12"})

        # ta_to_instructor_auto — پس از پایان ترم (flag)
        if extra.get("lms", {}).get("end_of_term_ta_evaluation_done") is True:
            hit = await _start_process_if_absent(
                db,
                student_id=st.id,
                process_code="ta_to_instructor_auto",
                initial_context={"source": "end_of_term_ta_evaluation_done"},
                fingerprint_key="ta_to_instructor_auto",
                fingerprint_val=str(extra.get("lms", {}).get("ta_evaluation_term") or today.year),
            )
            if hit:
                try:
                    from app.services.ta_to_instructor_auto_service import run_auto_ta_to_instructor_transition

                    inst = await db.get(ProcessInstance, uuid.UUID(hit["instance_id"]))
                    if inst:
                        to_state = await run_auto_ta_to_instructor_transition(db, inst)
                        if to_state:
                            hit = {**hit, "to_state": to_state}
                except Exception:
                    pass
                out.append({**hit, "trigger": "end_of_term_ta_evaluation_done"})

        # ta_to_assistant_faculty — ۲ بار موفق TA در یک درس (فرایند ۴۹)
        try:
            from app.services.ta_to_assistant_faculty_service import (
                _pick_qualifying_course,
                is_auto_blocked_for_course,
            )

            lms = extra.get("lms") if isinstance(extra.get("lms"), dict) else {}
            qualifying = _pick_qualifying_course(lms)
            if qualifying and lms.get("end_of_term_ta_evaluation_done") is True:
                course_code = str(qualifying.get("course_code") or "")
                if course_code and not is_auto_blocked_for_course(extra, course_code):
                    term_val = str(lms.get("ta_evaluation_term") or today.isoformat())[:7]
                    hit = await _start_process_if_absent(
                        db,
                        student_id=st.id,
                        process_code="ta_to_assistant_faculty",
                        initial_context={
                            "source": "end_of_term_ta_scan",
                            "course_code": course_code,
                        },
                        fingerprint_key=f"ta_to_assistant_faculty:{course_code}",
                        fingerprint_val=term_val,
                    )
                    if hit:
                        try:
                            from app.services.ta_to_assistant_faculty_service import propagate_on_start

                            inst = await db.get(ProcessInstance, uuid.UUID(hit["instance_id"]))
                            if inst:
                                to_state = await propagate_on_start(db, inst)
                                if to_state:
                                    hit = {**hit, "to_state": to_state}
                        except Exception:
                            pass
                        out.append({**hit, "trigger": "ta_passed_course_twice"})
        except Exception:
            logger.debug("ta_to_assistant_faculty scheduler skipped for student=%s", st.id)

    return out


async def dispatch_start_therapy_week9(db: AsyncSession, today: date) -> list[dict]:
    """``week9_deadline_exceeded`` برای نمونه‌های گیرکرده در eligibility_check."""
    out: list[dict] = []
    engine = StateMachineEngine(db)
    stmt = select(ProcessInstance).where(
        ProcessInstance.process_code == "start_therapy",
        ProcessInstance.current_state_code == "eligibility_check",
        ProcessInstance.is_completed.is_(False),
        ProcessInstance.is_cancelled.is_(False),
    )
    for instance in (await db.execute(stmt)).scalars().all():
        st = await db.get(Student, instance.student_id)
        if not st:
            continue
        extra = _student_extra(st)
        term_start = _parse_date(extra.get("term_start_date"))
        week = get_current_term_week(term_start=term_start, today=today)
        if week < 9:
            continue
        ctx = _context_as_dict(instance)
        if ctx.get("week9_blocked_fired"):
            continue
        try:
            r = await engine.execute_transition(
                instance_id=instance.id,
                trigger_event="week9_deadline_exceeded",
                actor_id=SYSTEM_ACTOR_ID,
                actor_role="system",
            )
            if r.success:
                ctx["week9_blocked_fired"] = True
                instance.context_data = ctx
                flag_modified(instance, "context_data")
                out.append({"instance_id": str(instance.id), "trigger": "week9_deadline_exceeded"})
        except Exception as e:
            logger.debug("week9_deadline_exceeded skipped: %s", e)
    return out


async def dispatch_lms_session_hooks(db: AsyncSession, now: datetime) -> list[dict]:
    """جلسات LMS: TA consultation، mentor session 2، class_attendance."""
    out: list[dict] = []
    engine = StateMachineEngine(db)
    today = now.date()
    stmt = select(Student).where(Student.is_sample_data.is_(False))
    students = list((await db.execute(stmt)).scalars().all())

    for st in students:
        extra = _student_extra(st)
        lms = extra.get("lms") or {}
        sessions = lms.get("course_sessions") or []

        for sess in sessions if isinstance(sessions, list) else []:
            if not isinstance(sess, dict):
                continue
            idx = sess.get("session_index") or sess.get("session_number")
            try:
                idx_i = int(idx)
            except (TypeError, ValueError):
                continue
            sess_date = _parse_date(sess.get("session_date") or sess.get("date"))
            if sess_date and sess_date > today:
                continue

            course_id = sess.get("course_id") or sess.get("course_code") or "default"

            # ta_student_consultation
            if idx_i in TA_CONSULTATION_SESSIONS and sess.get("ended") is True:
                fp = f"ta_consult:{course_id}:{idx_i}"
                hit = await _start_process_if_absent(
                    db,
                    student_id=st.id,
                    process_code="ta_student_consultation",
                    initial_context={"session_index": idx_i, "course_id": course_id},
                    fingerprint_key=fp,
                    fingerprint_val=sess_date.isoformat() if sess_date else str(idx_i),
                )
                if hit:
                    try:
                        await engine.execute_transition(
                            instance_id=uuid.UUID(hit["instance_id"]),
                            trigger_event="reminder_sent",
                            actor_id=SYSTEM_ACTOR_ID,
                            actor_role="system",
                        )
                    except Exception:
                        pass
                    out.append({**hit, "trigger": "session_5_or_10_or_15_ended", "session": idx_i})

            # mentor_private_sessions — جلسه ۲ بدون ثبت
            if idx_i == 2 and sess.get("started") is True:
                fp = f"mentor_s2:{course_id}"
                fps = extra.get("scheduler_fingerprints") or {}
                if fps.get(fp):
                    continue
                mentor_registered = lms.get("mentor_sessions_registered") is True
                if not mentor_registered:
                    hit = await _start_process_if_absent(
                        db,
                        student_id=st.id,
                        process_code="mentor_private_sessions",
                        initial_context={"course_id": course_id},
                        fingerprint_key=fp,
                        fingerprint_val=sess_date.isoformat() if sess_date else "s2",
                    )
                    if hit:
                        try:
                            await engine.execute_transition(
                                instance_id=uuid.UUID(hit["instance_id"]),
                                trigger_event="session_2_started_without_registration",
                                actor_id=SYSTEM_ACTOR_ID,
                                actor_role="system",
                            )
                        except Exception:
                            pass
                        out.append({**hit, "trigger": "session_2_started_without_registration"})

            # class_attendance — session_date reached
            if sess_date and sess_date <= today:
                fp = f"class_att:{course_id}:{sess_date.isoformat()}"
                fps = extra.get("scheduler_fingerprints") or {}
                if fps.get(fp):
                    continue
                from app.services.class_attendance_service import infer_course_type

                course_code = str(course_id)
                course_type = infer_course_type(course_code)
                hit = await _start_process_if_absent(
                    db,
                    student_id=st.id,
                    process_code="class_attendance",
                    initial_context={
                        "session_date": sess_date.isoformat(),
                        "course_id": course_id,
                        "course_code": course_code,
                        "lesson_name": course_code,
                        "lesson_course_label": course_code,
                        "course_type": course_type,
                    },
                    fingerprint_key=fp,
                    fingerprint_val=sess_date.isoformat(),
                )
                if hit:
                    try:
                        await engine.execute_transition(
                            instance_id=uuid.UUID(hit["instance_id"]),
                            trigger_event="session_time_reached",
                            actor_id=SYSTEM_ACTOR_ID,
                            actor_role="system",
                        )
                    except Exception:
                        pass
                    fps[fp] = sess_date.isoformat()
                    extra["scheduler_fingerprints"] = fps
                    st.extra_data = extra
                    flag_modified(st, "extra_data")
                    out.append({**hit, "trigger": "session_time_reached"})

            # skills_course_completion — جلسه ۱۷ و ۱۸
            if sess_date and sess_date <= today and idx_i in (17, 18):
                code_l = str(course_id).lower()
                is_skills = (
                    "skill" in code_l
                    or "مهارت" in str(course_id)
                    or "technique" in code_l
                    or "تکنیک" in str(course_id)
                )
                if is_skills:
                    from app.services.skills_course_completion_service import dispatch_skills_session_calendar

                    sk_hit = await dispatch_skills_session_calendar(
                        db,
                        st,
                        str(course_id),
                        idx_i,
                        sess_date.isoformat(),
                    )
                    if sk_hit:
                        out.append(sk_hit)
                elif idx_i == 18:
                    from app.services.theory_course_completion_service import (
                        dispatch_theory_session_calendar,
                        is_theory_course,
                    )

                    if is_theory_course(str(course_id)):
                        th_hit = await dispatch_theory_session_calendar(
                            db,
                            st,
                            str(course_id),
                            idx_i,
                            sess_date.isoformat(),
                        )
                        if th_hit:
                            out.append(th_hit)

    return out


def _part_count(part: Any) -> int:
    if isinstance(part, list):
        return len(part)
    if isinstance(part, dict):
        try:
            return int(part.get("created_total") or 0)
        except (TypeError, ValueError):
            return 0
    return 0


async def dispatch_semester_prep_starts(db: AsyncSession, today=None) -> list[dict]:
    """شروع خودکار آماده‌سازی پاییز (۱۵–۲۰ فروردین) و زمستان (پنجره قبل از شروع ترم)."""
    from app.utils.shamsi_calendar_utils import is_farvardin_15_20, tehran_today

    from app.services.semester_prep_service import (
        ensure_fall_prep_started,
        ensure_winter_prep_started,
        get_active_prep_instance,
        should_auto_start_winter,
        FALL_PREP,
        WINTER_PREP,
    )

    out: list[dict] = []
    ref = today or tehran_today()

    if is_farvardin_15_20(ref):
        active = await get_active_prep_instance(db, FALL_PREP)
        if active is None:
            try:
                hit = await ensure_fall_prep_started(db)
                out.append({**hit, "trigger": "farvardin_prep_window"})
            except Exception as e:
                logger.debug("ensure_fall_prep_started: %s", e)

    if await should_auto_start_winter(db, today=ref):
        try:
            hit = await ensure_winter_prep_started(db)
            out.append({**hit, "trigger": "winter_prep_window"})
        except Exception as e:
            logger.debug("ensure_winter_prep_started: %s", e)

    return out


async def run_process_scheduler_pass(db: AsyncSession) -> dict[str, Any]:
    """یک دور کامل موتور زمان‌بندی فرایند."""
    from app.utils.shamsi_calendar_utils import tehran_today

    now = datetime.now(timezone.utc)
    today = tehran_today()
    reminders = await dispatch_scheduled_reminders(db, now)
    installments = await dispatch_installment_overdue(db, today)
    sla = await dispatch_generic_sla_triggers(db, now)
    term_batch = await dispatch_academic_term_batch(db, now)
    milestones = await dispatch_student_milestones(db, today)
    week9 = await dispatch_start_therapy_week9(db, today)
    lms_hooks = await dispatch_lms_session_hooks(db, now)
    prep_starts = await dispatch_semester_prep_starts(db, today)
    parts = [reminders, installments, sla, term_batch, milestones, week9, lms_hooks, prep_starts]
    return {
        "scheduled_reminders": reminders,
        "installment_overdue": installments,
        "generic_sla_triggers": sla,
        "academic_term_batch": term_batch,
        "student_milestones": milestones,
        "start_therapy_week9": week9,
        "lms_session_hooks": lms_hooks,
        "semester_prep_starts": prep_starts,
        "scheduler_fired_total": sum(_part_count(p) for p in parts),
    }
