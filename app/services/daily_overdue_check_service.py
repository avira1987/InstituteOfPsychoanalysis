"""موتور چک روزانه کارهای عقب‌افتاده — SMS مکمل + نوتیفیکیشن ثبت‌شده در پنل."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.config import get_settings
from app.core.engine import StateMachineEngine
from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import (
    Assignment,
    AssignmentSubmission,
    DailyOverdueRunLog,
    InterviewSlot,
    PanelTaskReminder,
    ProcessInstance,
    Student,
    User,
)
from app.services.notification_service import notification_service
from app.services.operator_followup_inbox import _resolve_process_item
from app.services.process_role_user_resolver import resolve_first_user_for_assigned_role, resolve_users_for_assigned_role
from app.services.semester_prep_service import PREP_PROCESS_CODES

logger = logging.getLogger(__name__)

_REGISTRATION_PROCESS_CODES = frozenset(
    {
        "introductory_course_registration",
        "comprehensive_course_registration",
        "intro_second_semester_registration",
    }
)

_CONTEXT_DEADLINE_FIELDS = (
    ("documents_correction_deadline", None),
    ("return_deadline_at", frozenset({"on_leave", "return_reminder_sent"})),
)


def _tehran_now() -> datetime:
    tz = ZoneInfo(get_settings().DAILY_OVERDUE_CHECK_TZ)
    return datetime.now(tz)


def _tehran_today() -> date:
    return _tehran_now().date()


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
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except Exception:
            return None
    return None


def _context_as_dict(instance: ProcessInstance) -> dict[str, Any]:
    return StateMachineEngine._as_mapping(instance.context_data)


@dataclass
class OverdueTask:
    kind: str
    task_key: str
    assigned_role: str
    student_id: str
    instance_id: Optional[str] = None
    process_code: Optional[str] = None
    state_code: Optional[str] = None
    process_name_fa: str = ""
    state_name_fa: str = ""
    student_code: str = ""
    student_name: str = ""
    task_title: str = ""
    overdue_reason: str = ""
    raw_item: dict[str, Any] = field(default_factory=dict)


def _is_prep_process(process_code: str | None) -> bool:
    return (process_code or "") in PREP_PROCESS_CODES


def _prep_task_key(instance_id: str, state_code: str) -> str:
    return f"prep:{instance_id}:{state_code}"


def _prep_display_name(proc_name: str, st_name: str) -> str:
    return f"آماده‌سازی — {st_name or proc_name}"


def _fingerprint(run_date: date, task_key: str) -> str:
    return f"daily_overdue:{run_date.isoformat()}:{task_key}"


def _fingerprint_for_user(run_date: date, task_key: str, user_id: uuid.UUID) -> str:
    return f"daily_overdue:{run_date.isoformat()}:{task_key}:user:{user_id}"


def _task_to_raw_item(task: OverdueTask) -> dict[str, Any]:
    if task.raw_item:
        return task.raw_item
    kind = task.kind
    if kind in ("semester_prep_sla", "prep_calendar_deadline"):
        kind = "semester_prep_sla"
    elif _is_prep_process(task.process_code) and kind == "process_sla":
        kind = "semester_prep_sla"
    if task.kind == "assignment_grading":
        return {
            "kind": "assignment_grading",
            "assignment_id": task.task_key.split(":")[-1] if ":" in task.task_key else None,
            "submission_id": task.task_key,
            "student_id": task.student_id,
            "student_code": task.student_code,
            "title_fa": task.task_title,
            "responsible_role_code": task.assigned_role,
        }
    return {
        "kind": kind,
        "instance_id": task.instance_id,
        "student_id": task.student_id,
        "student_code": task.student_code,
        "process_code": task.process_code,
        "process_name_fa": task.process_name_fa,
        "state_code": task.state_code,
        "state_name_fa": task.state_name_fa,
        "responsible_role_code": task.assigned_role,
    }


async def collect_overdue_tasks(
    db: AsyncSession,
    *,
    now: Optional[datetime] = None,
    today: Optional[date] = None,
    scan_cap: int = 2000,
) -> list[OverdueTask]:
    """شناسایی کارهای عقب‌افتاده از SLA، context، قسط، حضور درمان، تکلیف."""
    now = now or datetime.now(timezone.utc)
    today = today or now.date()
    sd = aliased(StateDefinition)
    pd = aliased(ProcessDefinition)
    tasks: list[OverdueTask] = []
    seen_keys: set[str] = set()

    def _add(task: OverdueTask) -> None:
        if task.task_key in seen_keys:
            return
        seen_keys.add(task.task_key)
        tasks.append(task)

    stmt = (
        select(ProcessInstance, Student, pd, sd, User)
        .join(Student, ProcessInstance.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .join(pd, ProcessInstance.process_code == pd.code)
        .outerjoin(
            sd,
            (sd.process_id == pd.id) & (sd.code == ProcessInstance.current_state_code),
        )
        .where(
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
            Student.is_sample_data.is_(False),
        )
        .order_by(desc(ProcessInstance.last_transition_at))
        .limit(scan_cap)
    )
    rows = (await db.execute(stmt)).all()

    for pi, student, proc_def, state_def, st_user in rows:
        st_code = (pi.current_state_code or "").strip()
        ctx = _context_as_dict(pi)
        proc_name = proc_def.name_fa if proc_def else pi.process_code
        st_name = state_def.name_fa if state_def else st_code
        is_prep = _is_prep_process(pi.process_code)
        student_name = (st_user.full_name_fa or "").strip() or student.student_code
        if is_prep:
            student_name = "انستیتو"
        base_kwargs = dict(
            student_id=str(student.id),
            instance_id=str(pi.id),
            process_code=pi.process_code,
            state_code=st_code,
            process_name_fa=proc_name or pi.process_code,
            state_name_fa=st_name,
            student_code=student.student_code,
            student_name=student_name,
        )

        assigned_role = (state_def.assigned_role if state_def else None) or ""
        resolved = _resolve_process_item(assigned_role or None, st_code, False)
        if resolved is None:
            role_code = "student"
        else:
            role_code, _, _ = resolved

        if is_prep and st_code == "calendar_entry":
            cal_dl = _parse_iso_datetime(ctx.get("calendar_sla_deadline_at"))
            if cal_dl and now > cal_dl:
                _add(
                    OverdueTask(
                        kind="prep_calendar_deadline",
                        task_key=_prep_task_key(str(pi.id), st_code),
                        assigned_role=role_code,
                        task_title=_prep_display_name(proc_name, st_name),
                        overdue_reason="مهلت تدوین تقویم (۲۰ فروردین) گذشته",
                        **base_kwargs,
                    )
                )

        if state_def and state_def.sla_hours:
            elapsed_h = (now - pi.last_transition_at).total_seconds() / 3600
            if elapsed_h > state_def.sla_hours:
                sla_kind = "semester_prep_sla" if is_prep else "process_sla"
                task_key = (
                    _prep_task_key(str(pi.id), st_code)
                    if is_prep
                    else f"sla:{pi.id}:{st_code}"
                )
                _add(
                    OverdueTask(
                        kind=sla_kind,
                        task_key=task_key,
                        assigned_role=role_code,
                        task_title=_prep_display_name(proc_name, st_name) if is_prep else (st_name or st_code),
                        overdue_reason=f"مهلت SLA ({state_def.sla_hours} ساعت) گذشته",
                        **base_kwargs,
                    )
                )

        if (
            pi.process_code in _REGISTRATION_PROCESS_CODES
            and st_code == "registration_complete"
        ):
            due = _parse_date(ctx.get("next_installment_due_at"))
            if due is not None and due <= today:
                _add(
                    OverdueTask(
                        kind="installment",
                        task_key=f"installment:{pi.id}",
                        assigned_role="student",
                        task_title="پرداخت قسط ثبت‌نام",
                        overdue_reason=f"سررسید قسط ({due.isoformat()}) گذشته",
                        **base_kwargs,
                    )
                )

        for field_name, allowed_states in _CONTEXT_DEADLINE_FIELDS:
            raw_deadline = ctx.get(field_name)
            if allowed_states is not None and st_code not in allowed_states:
                continue
            deadline_dt = _parse_iso_datetime(raw_deadline)
            deadline_d = _parse_date(raw_deadline)
            is_past = False
            if deadline_dt and deadline_dt <= now:
                is_past = True
            elif deadline_d and deadline_d <= today:
                is_past = True
            if is_past:
                _add(
                    OverdueTask(
                        kind="context_deadline",
                        task_key=f"ctx:{pi.id}:{field_name}",
                        assigned_role=role_code,
                        task_title=st_name or field_name,
                        overdue_reason=f"مهلت {field_name} گذشته",
                        **base_kwargs,
                    )
                )

        if pi.process_code == "attendance_tracking" and st_code == "therapist_recording":
            session_d = _parse_date(ctx.get("session_date"))
            if session_d:
                deadline = datetime.combine(session_d, time.min, tzinfo=timezone.utc) + timedelta(hours=24)
                if now >= deadline:
                    _add(
                        OverdueTask(
                            kind="therapist_recording_24h",
                            task_key=f"att24:{pi.id}",
                            assigned_role="therapist",
                            task_title="ثبت حضور جلسه درمان",
                            overdue_reason="بیش از ۲۴ ساعت از تاریخ جلسه گذشته",
                            **base_kwargs,
                        )
                    )

    sub_stmt = (
        select(AssignmentSubmission, Assignment, Student, User)
        .join(Assignment, AssignmentSubmission.assignment_id == Assignment.id)
        .join(Student, AssignmentSubmission.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .where(
            AssignmentSubmission.score.is_(None),
            AssignmentSubmission.body_text.isnot(None),
            AssignmentSubmission.body_text != "",
            Student.is_sample_data.is_(False),
        )
        .order_by(AssignmentSubmission.submitted_at.asc())
        .limit(200)
    )
    for sub, assign, student, st_user in (await db.execute(sub_stmt)).all():
        submitted = sub.submitted_at or datetime.now(timezone.utc)
        if submitted.tzinfo is None:
            submitted = submitted.replace(tzinfo=timezone.utc)
        if (now - submitted).total_seconds() < 86400:
            continue
        student_name = (st_user.full_name_fa or "").strip() or student.student_code
        _add(
            OverdueTask(
                kind="assignment_grading",
                task_key=f"assign:{sub.id}",
                assigned_role="instructor",
                student_id=str(student.id),
                task_title=assign.title_fa or "تکلیف",
                student_code=student.student_code,
                student_name=student_name,
                overdue_reason="تکلیف ارسال‌شده بیش از ۲۴ ساعت بدون نمره",
                raw_item={
                    "kind": "assignment_grading",
                    "assignment_id": str(assign.id),
                    "submission_id": str(sub.id),
                    "student_id": str(student.id),
                    "student_code": student.student_code,
                    "title_fa": assign.title_fa,
                    "responsible_role_code": "instructor",
                },
            )
        )

    return tasks


async def _resolve_user_for_role(
    db: AsyncSession,
    role: str,
    *,
    student: Optional[Student] = None,
    instance: Optional[ProcessInstance] = None,
) -> Optional[User]:
    role = (role or "").strip().lower()
    if role in ("student", "applicant"):
        if student is None:
            return None
        r = await db.execute(select(User).where(User.id == student.user_id))
        return r.scalars().first()

    if role == "therapist":
        tid = student.therapist_id if student else None
        if not tid and instance is not None:
            ctx = _context_as_dict(instance)
            raw = ctx.get("therapist_id")
            if raw:
                try:
                    tid = uuid.UUID(str(raw))
                except (ValueError, TypeError):
                    tid = None
        if tid:
            r = await db.execute(select(User).where(User.id == tid, User.is_active.is_(True)))
            return r.scalars().first()

    if role == "supervisor" and student and student.supervisor_id:
        r = await db.execute(
            select(User).where(User.id == student.supervisor_id, User.is_active.is_(True))
        )
        return r.scalars().first()

    if role == "interviewer" and instance is not None:
        ctx = _context_as_dict(instance)
        iuid = ctx.get("interviewer_user_id")
        if iuid:
            try:
                r = await db.execute(
                    select(User).where(User.id == uuid.UUID(str(iuid)), User.is_active.is_(True))
                )
                u = r.scalars().first()
                if u:
                    return u
            except (ValueError, TypeError):
                pass
        r = await db.execute(
            select(InterviewSlot.interviewer_user_id)
            .where(InterviewSlot.assigned_instance_id == instance.id)
            .where(InterviewSlot.interviewer_user_id.isnot(None))
            .limit(1)
        )
        row = r.scalars().first()
        if row is not None:
            r2 = await db.execute(select(User).where(User.id == row, User.is_active.is_(True)))
            return r2.scalars().first()

    mapped = await resolve_first_user_for_assigned_role(db, role)
    if mapped is not None:
        return mapped

    if role in (
        "site_manager",
        "deputy_education",
        "monitoring_committee_officer",
        "therapy_committee_chair",
        "therapy_committee_executor",
        "admin",
        "staff",
        "finance",
        "instructor",
        "admissions_officer",
        "scientific_officer_course_committee",
        "deputy_education_director",
        "course_committee_executive",
    ):
        r = await db.execute(select(User).where(User.role == role, User.is_active.is_(True)).limit(1))
        return r.scalars().first()

    return None


async def _resolve_contact_phone(user: Optional[User]) -> Optional[str]:
    if not user:
        return None
    return (user.phone or user.email or "").strip() or None


async def _existing_fingerprints(db: AsyncSession, run_date: date) -> set[str]:
    r = await db.execute(
        select(PanelTaskReminder.fingerprint).where(PanelTaskReminder.run_date_tehran == run_date)
    )
    return {row[0] for row in r.all()}


async def already_ran_scheduler_today(db: AsyncSession, run_date: date) -> bool:
    r = await db.execute(
        select(DailyOverdueRunLog.id)
        .where(
            DailyOverdueRunLog.run_date_tehran == run_date,
            DailyOverdueRunLog.triggered_by == "scheduler",
        )
        .limit(1)
    )
    return r.scalars().first() is not None


async def dispatch_daily_reminders(
    db: AsyncSession,
    tasks: list[OverdueTask],
    *,
    run_date: date,
    existing_fps: Optional[set[str]] = None,
) -> dict[str, Any]:
    """SMS + ثبت PanelTaskReminder با dedup روزانه."""
    existing = existing_fps if existing_fps is not None else await _existing_fingerprints(db, run_date)
    sms_sent = 0
    notifications_created = 0
    skipped_dedup = 0
    details: list[dict[str, Any]] = []
    errors: list[str] = []

    instance_cache: dict[str, tuple[ProcessInstance, Student]] = {}

    for task in tasks:
        student: Optional[Student] = None
        instance: Optional[ProcessInstance] = None
        if task.instance_id:
            if task.instance_id in instance_cache:
                instance, student = instance_cache[task.instance_id]
            else:
                r = await db.execute(
                    select(ProcessInstance, Student)
                    .join(Student, ProcessInstance.student_id == Student.id)
                    .where(ProcessInstance.id == uuid.UUID(task.instance_id))
                )
                row = r.first()
                if row:
                    instance, student = row
                    instance_cache[task.instance_id] = (instance, student)
        elif task.student_id:
            r = await db.execute(select(Student).where(Student.id == uuid.UUID(task.student_id)))
            student = r.scalars().first()

        is_prep = _is_prep_process(task.process_code)
        users = (
            await resolve_users_for_assigned_role(db, task.assigned_role)
            if is_prep
            else []
        )
        if not users:
            single = await _resolve_user_for_role(
                db, task.assigned_role, student=student, instance=instance
            )
            users = [single] if single else []

        if not users:
            errors.append(f"no_user:{task.task_key}:{task.assigned_role}")
            continue

        for user in users:
            fp = (
                _fingerprint_for_user(run_date, task.task_key, user.id)
                if is_prep
                else _fingerprint(run_date, task.task_key)
            )
            if fp in existing:
                skipped_dedup += 1
                continue

            raw = _task_to_raw_item(task)
            from app.services.panel_action_notifications import notification_action_path

            action_path = notification_action_path(raw)
            if task.assigned_role in ("student", "applicant") and task.instance_id:
                from urllib.parse import urlencode

                q = urlencode({"tab": "processes", "instance_id": task.instance_id})
                action_path = f"/panel/portal/student?{q}"

            title = f"کار عقب‌افتاده — {task.process_name_fa or task.task_title}"
            if is_prep:
                title = f"آماده‌سازی ترم — {task.state_name_fa or task.task_title}"
            if task.kind == "assignment_grading":
                title = f"تصحیح تکلیف عقب‌افتاده — {task.student_code}"
            summary = (
                f"{task.overdue_reason}. "
                f"{'فرایند: ' + (task.process_name_fa or '') + ' — ' if task.process_name_fa else ''}"
                f"{'مرحله: «' + task.state_name_fa + '» — ' if task.state_name_fa else ''}"
                f"لطفاً در پنل تکمیل کنید."
            )

            phone = await _resolve_contact_phone(user)
            sms_at = None
            if phone:
                try:
                    await notification_service.send_notification(
                        "sms",
                        "daily_overdue_reminder",
                        phone,
                        {
                            "task_title": task.task_title or task.state_name_fa or "اقدام معوق",
                            "process_name_fa": task.process_name_fa or task.process_code or "فرایند",
                            "student_name": task.student_name or task.student_code or "دانشجو",
                            "state_label_fa": task.state_name_fa or "",
                        },
                    )
                    sms_at = datetime.now(timezone.utc)
                    sms_sent += 1
                except Exception as e:
                    errors.append(f"sms_fail:{task.task_key}:{e}")

            reminder = PanelTaskReminder(
                user_id=user.id,
                kind="daily_overdue",
                title_fa=title,
                summary_fa=summary,
                action_path=action_path,
                instance_id=uuid.UUID(task.instance_id) if task.instance_id else None,
                student_id=uuid.UUID(task.student_id) if task.student_id else None,
                process_code=task.process_code,
                state_code=task.state_code,
                responsible_role_code=task.assigned_role,
                source="daily_overdue_check",
                run_date_tehran=run_date,
                sms_sent_at=sms_at,
                fingerprint=fp,
            )
            db.add(reminder)
            existing.add(fp)
            notifications_created += 1
            details.append(
                {
                    "task_key": task.task_key,
                    "kind": task.kind,
                    "user_id": str(user.id),
                    "student_code": task.student_code,
                    "process_code": task.process_code,
                    "state_code": task.state_code,
                    "assigned_role": task.assigned_role,
                    "sms_sent": sms_at is not None,
                    "action_path": action_path,
                }
            )

    return {
        "sms_sent": sms_sent,
        "notifications_created": notifications_created,
        "skipped_dedup": skipped_dedup,
        "details": details,
        "errors": errors,
    }


async def run_daily_overdue_check_pass(
    db: AsyncSession,
    *,
    triggered_by: str = "scheduler",
    force: bool = False,
) -> dict[str, Any]:
    """یک دور کامل: scan → SMS → panel reminders → run log."""
    run_date = _tehran_today()
    started = datetime.now(timezone.utc)

    if triggered_by == "scheduler" and not force:
        if await already_ran_scheduler_today(db, run_date):
            return {
                "skipped": True,
                "reason": "already_ran_today",
                "run_date_tehran": run_date.isoformat(),
            }

    log = DailyOverdueRunLog(
        run_date_tehran=run_date,
        started_at=started,
        triggered_by=triggered_by,
    )
    db.add(log)
    await db.flush()

    try:
        tasks = await collect_overdue_tasks(db)
        dispatch = await dispatch_daily_reminders(db, tasks, run_date=run_date)
        log.tasks_found = len(tasks)
        log.sms_sent = dispatch["sms_sent"]
        log.notifications_created = dispatch["notifications_created"]
        log.skipped_dedup = dispatch["skipped_dedup"]
        log.errors_json = {
            "errors": dispatch.get("errors") or [],
            "details": dispatch.get("details") or [],
        }
    except Exception as e:
        logger.exception("daily_overdue_check failed")
        log.errors_json = {"fatal": str(e)}
        log.tasks_found = 0
        raise
    finally:
        log.finished_at = datetime.now(timezone.utc)

    return {
        "skipped": False,
        "run_id": str(log.id),
        "run_date_tehran": run_date.isoformat(),
        "tasks_found": log.tasks_found,
        "sms_sent": log.sms_sent,
        "notifications_created": log.notifications_created,
        "skipped_dedup": log.skipped_dedup,
        "triggered_by": triggered_by,
        "errors": (log.errors_json or {}).get("errors") or [],
        "details": (log.errors_json or {}).get("details") or [],
    }


async def maybe_run_daily_overdue_check(db: AsyncSession) -> Optional[dict[str, Any]]:
    """در انتهای calendar pass — فقط پس از ساعت محلی تنظیم‌شده."""
    settings = get_settings()
    if not getattr(settings, "DAILY_OVERDUE_CHECK_ENABLED", True):
        return None
    now_tehran = _tehran_now()
    if now_tehran.hour < settings.DAILY_OVERDUE_CHECK_LOCAL_HOUR:
        return None
    return await run_daily_overdue_check_pass(db, triggered_by="scheduler")


async def list_daily_overdue_runs(
    db: AsyncSession,
    *,
    limit: int = 30,
) -> list[dict[str, Any]]:
    r = await db.execute(
        select(DailyOverdueRunLog)
        .order_by(desc(DailyOverdueRunLog.started_at))
        .limit(min(max(limit, 1), 100))
    )
    out: list[dict[str, Any]] = []
    for row in r.scalars().all():
        err = row.errors_json or {}
        out.append(
            {
                "id": str(row.id),
                "run_date_tehran": row.run_date_tehran.isoformat(),
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "finished_at": row.finished_at.isoformat() if row.finished_at else None,
                "tasks_found": row.tasks_found,
                "sms_sent": row.sms_sent,
                "notifications_created": row.notifications_created,
                "skipped_dedup": row.skipped_dedup,
                "triggered_by": row.triggered_by,
                "errors": err.get("errors") or [],
                "details": err.get("details") or [],
            }
        )
    return out
