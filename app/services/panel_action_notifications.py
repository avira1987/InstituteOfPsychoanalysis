"""فید یکپارچهٔ اعلان‌های اقدام برای زنگوله و صفحهٔ «همه اعلان‌ها» — هم‌راستا با my-operator-followup + نوبت دانشجو."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import desc, select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.meta_models import ProcessDefinition, StateDefinition
from app.models.operational_models import ProcessInstance, Student, User, InterviewSlot
from app.services.panel_task_reminders import load_active_panel_reminders
from app.services.panel_flash_messages import load_panel_flash_messages
from app.services.panel_notification_dismiss import (
    filter_dismissed_items,
    load_dismissed_notification_ids,
    prune_stale_task_reminders,
)
from app.services.operator_readiness import compute_operator_readiness_alerts
from app.services.portal_role_inbox import build_portal_role_process_inbox
from app.core.portal_role_home import (
    committee_kind_for_assigned_role,
    committee_kind_path,
    staff_lane_for_assigned_role,
    staff_lane_path,
)

_COMMITTEE_ROLES = frozenset(
    {
        "committee",
        "progress_committee",
        "education_committee",
        "supervision_committee",
        "specialized_commission",
        "therapy_committee_chair",
        "therapy_committee_executor",
        "deputy_education",
        "monitoring_committee_officer",
    }
)

_STAFF_LIKE = frozenset(
    {
        "staff",
        "finance",
        "admissions_officer",
        "instructor",
        "scientific_officer_course_committee",
        "deputy_education_director",
    }
)


def _path_query(path: str, params: dict[str, Any]) -> str:
    clean = {k: v for k, v in params.items() if v is not None and v != ""}
    q = urlencode(clean)
    return f"{path}?{q}" if q else path


def notification_action_path(item: dict[str, Any]) -> str:
    """هم‌تراز admin-ui/src/utils/operatorFollowupDeepLinks.js — مسیر SPA بدون nf."""
    kind = item.get("kind")
    if kind == "readiness":
        href = (item.get("action_href") or "/panel/profile").strip()
        if not href.startswith("/"):
            href = "/" + href.lstrip("/")
        return href
    if kind == "assignment_grading":
        return _path_query(
            staff_lane_path("instruction"),
            {
                "tab": "dashboard",
                "student_id": item.get("student_id"),
                "assignment_id": item.get("assignment_id"),
            },
        )
    if kind == "interview_booking":
        ap = (item.get("action_path") or "").strip()
        if ap:
            return ap if ap.startswith("/") else "/" + ap.lstrip("/")
        return "/panel/portal/interviewer"
    if kind == "daily_overdue":
        ap = (item.get("action_path") or "").strip()
        if ap:
            return ap if ap.startswith("/") else "/" + ap.lstrip("/")
        return "/panel/notifications"
    if kind == "semester_prep_sla":
        instance_id = item.get("instance_id")
        student_id = item.get("student_id")
        state_code = (item.get("state_code") or "").strip().lower()
        process_code = (item.get("process_code") or "").strip().lower()
        code = (item.get("responsible_role_code") or "").strip().lower()
        if (
            process_code == "fall_semester_preparation"
            and state_code == "calendar_entry"
            and code
            in (
                "course_committee_executive",
                "deputy_education",
                "deputy_education_director",
            )
        ):
            return "/panel/semester-prep/calendar"
        if (
            process_code == "winter_semester_preparation"
            and state_code == "course_list_review"
            and code
            in (
                "scientific_officer_course_committee",
                "deputy_education",
                "deputy_education_director",
                "course_committee_scientific",
            )
        ):
            return "/panel/semester-prep/course-list-review"
        base = {"instance_id": instance_id, "student_id": student_id, "tab": "reviews"}
        if code == "site_manager":
            return _path_query("/panel/portal/site-manager", {**base, "tab": "pending"})
        if code in _COMMITTEE_ROLES or code in (
            "deputy_education_director",
            "course_committee_executive",
            "scientific_officer_course_committee",
        ):
            return _path_query(
                committee_kind_path(committee_kind_for_assigned_role(code or "deputy_education")),
                base,
            )
        if code in _STAFF_LIKE or code == "admissions_officer":
            lane = staff_lane_for_assigned_role(code or "admissions_officer")
            return _path_query(staff_lane_path(lane), {**base, "tab": "pending"})
        return _path_query("/panel/semester-prep", {})

    instance_id = item.get("instance_id")
    student_id = item.get("student_id")
    code = (item.get("responsible_role_code") or "").strip().lower()
    process_code = (item.get("process_code") or "").strip().lower()
    state_code = (item.get("state_code") or "").strip().lower()
    base = {"instance_id": instance_id, "student_id": student_id}

    if code in ("student", "applicant"):
        return _path_query(
            "/panel/portal/student",
            {**base, "tab": "processes", "process_code": process_code or None},
        )

    if not instance_id or not student_id:
        if process_code in ("fall_semester_preparation", "winter_semester_preparation"):
            return "/panel/semester-prep"
        return _path_query("/panel/students", {"student_id": student_id, "instance_id": instance_id})

    if (
        process_code == "introductory_course_registration"
        and state_code == "documents_review"
    ):
        return _path_query(
            staff_lane_path("admissions"),
            {**base, "tab": "documentsReview"},
        )

    if code == "therapist":
        return _path_query("/panel/portal/therapist", {**base, "tab": "pending"})
    if code == "supervisor":
        return _path_query("/panel/portal/supervisor", {**base, "tab": "reviews"})
    if code == "site_manager":
        return _path_query("/panel/portal/site-manager", {**base, "tab": "pending"})
    if code in _COMMITTEE_ROLES:
        return _path_query(
            committee_kind_path(committee_kind_for_assigned_role(code)),
            {**base, "tab": "reviews"},
        )
    if code == "interviewer":
        return _path_query(staff_lane_path("admissions"), {**base, "tab": "pending"})
    if code in _STAFF_LIKE:
        lane = staff_lane_for_assigned_role(code)
        return _path_query(staff_lane_path(lane), {**base, "tab": "pending"})
    return _path_query("/panel/students", {"student_id": student_id, "instance_id": instance_id})


def _merge_readiness_into_inbox_items(
    core_items: list[dict[str, Any]],
    alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not alerts:
        return list(core_items)
    now_iso = datetime.now(timezone.utc).isoformat()
    extra: list[dict[str, Any]] = []
    for a in alerts:
        extra.append(
            {
                "kind": "readiness",
                "readiness_id": str(a.get("id", "")),
                "title_fa": a.get("title_fa") or "",
                "detail_fa": a.get("detail_fa") or "",
                "action_href": a.get("action_href") or "",
                "action_label_fa": a.get("action_label_fa") or "",
                "severity": a.get("severity") or "warning",
                "sort_at": now_iso,
            }
        )
    merged = extra + list(core_items)

    def _sk(x: dict[str, Any]) -> tuple[int, str]:
        return (0 if x.get("kind") == "readiness" else 1, x.get("sort_at") or "")

    merged.sort(key=_sk)
    return merged


def _summary_fa_for_operator_process(it: dict[str, Any]) -> str:
    st = (it.get("state_name_fa") or it.get("state_code") or "").strip()
    role = (it.get("responsible_role_label_fa") or "").strip()
    code = (it.get("student_code") or "").strip()
    parts = [
        f"فرایند: {it.get('process_name_fa') or it.get('process_code') or '—'}",
    ]
    if code:
        parts.append(f"دانشجو: {code}")
    if st:
        parts.append(f"مرحله فعلی: «{st}»")
    if role:
        parts.append(f"نقش مسئول در سیستم: {role}")
    parts.append("طبق این مرحله در پنل مربوطه اقدام را انجام دهید.")
    return " — ".join(parts)


def _normalize_raw_to_notification(raw: dict[str, Any]) -> dict[str, Any] | None:
    kind = raw.get("kind")
    if kind == "readiness":
        rid = raw.get("readiness_id") or "unknown"
        title = (raw.get("title_fa") or "").strip() or "هشدار آمادگی"
        detail = (raw.get("detail_fa") or "").strip()
        summary = detail or title
        return {
            "notification_id": f"readiness:{rid}",
            "kind": "readiness",
            "title_fa": title,
            "summary_fa": summary,
            "action_path": notification_action_path(raw),
            "sort_at": raw.get("sort_at") or "",
            "instance_id": None,
            "student_id": None,
        }
    if kind == "assignment_grading":
        sid = raw.get("submission_id") or "unknown"
        title_fa = (raw.get("title_fa") or "").strip() or "تکلیف"
        code = (raw.get("student_code") or "").strip()
        summary = f"تصحیح تکلیف «{title_fa}» را برای دانشجو {code or '—'} ثبت کنید."
        return {
            "notification_id": f"assignment_grading:{sid}",
            "kind": "assignment_grading",
            "title_fa": f"تصحیح تکلیف — {code or 'دانشجو'}",
            "summary_fa": summary,
            "action_path": notification_action_path(raw),
            "sort_at": raw.get("sort_at") or "",
            "instance_id": None,
            "student_id": raw.get("student_id"),
        }
    if kind == "process":
        iid = raw.get("instance_id")
        if not iid:
            return None
        code = (raw.get("student_code") or "").strip()
        title = f"{raw.get('process_name_fa') or raw.get('process_code') or 'فرایند'} — {code or 'دانشجو'}"
        return {
            "notification_id": f"process:{iid}",
            "kind": "process",
            "title_fa": title,
            "summary_fa": _summary_fa_for_operator_process(raw),
            "action_path": notification_action_path(raw),
            "sort_at": raw.get("sort_at") or "",
            "instance_id": str(iid),
            "student_id": raw.get("student_id"),
        }
    return None


async def _student_pending_notification_sources(
    db: AsyncSession,
    user: User,
    *,
    scan_cap: int = 400,
) -> list[tuple[ProcessInstance, ProcessDefinition, StateDefinition]]:
    r = await db.execute(select(Student).where(Student.user_id == user.id))
    student = r.scalars().first()
    if not student:
        return []

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
        .limit(scan_cap)
    )
    res = await db.execute(stmt)
    out: list[tuple[ProcessInstance, ProcessDefinition, StateDefinition]] = []
    for pi, proc_def, state_def in res.all():
        if state_def is None:
            continue
        ar = (state_def.assigned_role or "").strip().lower()
        if ar not in ("student", "applicant"):
            continue
        out.append((pi, proc_def, state_def))
    return out


def _student_notification_record(
    student: Student,
    pi: ProcessInstance,
    proc_def: ProcessDefinition,
    state_def: StateDefinition,
) -> dict[str, Any]:
    meta = state_def.metadata_ if isinstance(state_def.metadata_, dict) else {}
    short = (meta.get("student_short_fa") or meta.get("student_guidance_fa") or "").strip()
    summary = short or (
        f"در فرایند «{proc_def.name_fa}» مرحلهٔ «{state_def.name_fa}» را در پنل آموزشی تکمیل کنید."
    )
    sort_at = (
        pi.last_transition_at.isoformat()
        if pi.last_transition_at
        else (pi.started_at.isoformat() if pi.started_at else "")
    )
    action_path = _path_query(
        "/panel/portal/student",
        {"tab": "processes", "instance_id": str(pi.id)},
    )
    title = f"{proc_def.name_fa} — {student.student_code}"
    return {
        "notification_id": f"process:{pi.id}",
        "kind": "process",
        "title_fa": title,
        "summary_fa": summary,
        "action_path": action_path,
        "sort_at": sort_at,
        "instance_id": str(pi.id),
        "student_id": str(student.id),
    }


async def _upcoming_paid_interview_slot_notifications(
    db: AsyncSession,
    user: User,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """اسلات‌های مصاحبهٔ پرداخت‌تأییدشدهٔ آینده برای مصاحبه‌گر/کارمند."""
    role = (user.role or "").strip().lower()
    if role not in ("interviewer", "staff", "admin", "site_manager", "deputy_education"):
        return []
    now = now or datetime.now(timezone.utc)
    su = aliased(User)
    stmt = (
        select(InterviewSlot, Student, su)
        .join(Student, InterviewSlot.assigned_student_id == Student.id)
        .join(su, Student.user_id == su.id)
        .where(
            InterviewSlot.assigned_student_id.isnot(None),
            InterviewSlot.booking_payment_deadline_at.is_(None),
            InterviewSlot.ends_at >= now,
        )
    )
    if role == "interviewer":
        stmt = stmt.where(
            or_(
                InterviewSlot.interviewer_user_id == user.id,
                and_(
                    InterviewSlot.interviewer_user_id.is_(None),
                    InterviewSlot.created_by == user.id,
                ),
            )
        )
    stmt = stmt.order_by(InterviewSlot.starts_at).limit(80)
    rows = (await db.execute(stmt)).all()
    out: list[dict[str, Any]] = []
    for slot, student, st_user in rows:
        st_iso = slot.starts_at.isoformat() if slot.starts_at else ""
        mode_fa = "آنلاین" if slot.mode == "online" else "حضوری"
        code = (student.student_code or "").strip()
        name = (st_user.full_name_fa or "").strip() or code or "دانشجو"
        title = f"مصاحبه پذیرش — {name}"
        loc_part = ""
        if slot.mode == "online":
            loc_part = "جلسه آنلاین؛ جزئیات در پنل وقت مصاحبه."
        else:
            loc_part = ((slot.location_fa or "").strip() or "حضوری در انستیتو")
        summary = f"{mode_fa} · {st_iso[:19].replace('T', ' ')} · {loc_part}"
        iid = str(slot.assigned_instance_id) if slot.assigned_instance_id else None
        sid = str(student.id)
        if role == "interviewer":
            href = "/panel/portal/interviewer"
            action_path = _path_query(href, {"student_id": sid, "instance_id": iid} if iid else {"student_id": sid})
        else:
            action_path = _path_query("/panel/students", {"student_id": sid, "instance_id": iid})
        out.append(
            {
                "notification_id": f"interview_booking:{slot.id}",
                "kind": "interview_booking",
                "title_fa": title,
                "summary_fa": summary,
                "action_path": action_path,
                "sort_at": st_iso,
                "instance_id": iid,
                "student_id": sid,
            }
        )
    return out


async def _pending_payment_interview_slot_notifications(
    db: AsyncSession,
    user: User,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """اسلات‌های در انتظار پرداخت برای مصاحبه‌گر اختصاص‌یافته."""
    role = (user.role or "").strip().lower()
    if role != "interviewer":
        return []
    now = now or datetime.now(timezone.utc)
    su = aliased(User)
    stmt = (
        select(InterviewSlot, Student, su)
        .join(Student, InterviewSlot.assigned_student_id == Student.id)
        .join(su, Student.user_id == su.id)
        .where(
            InterviewSlot.interviewer_user_id == user.id,
            InterviewSlot.assigned_student_id.isnot(None),
            InterviewSlot.booking_payment_deadline_at.isnot(None),
            InterviewSlot.ends_at >= now,
        )
        .order_by(InterviewSlot.starts_at)
        .limit(40)
    )
    rows = (await db.execute(stmt)).all()
    out: list[dict[str, Any]] = []
    for slot, student, st_user in rows:
        st_iso = slot.starts_at.isoformat() if slot.starts_at else ""
        mode_fa = "آنلاین" if slot.mode == "online" else "حضوری"
        name = (st_user.full_name_fa or "").strip() or (student.student_code or "").strip() or "دانشجو"
        title = f"انتخاب وقت — {name}"
        summary = (
            f"{mode_fa} · {st_iso[:19].replace('T', ' ')} · "
            "دانشجو وقت را انتخاب کرده؛ در انتظار پرداخت (۱۰ دقیقه)."
        )
        iid = str(slot.assigned_instance_id) if slot.assigned_instance_id else None
        sid = str(student.id)
        action_path = _path_query(
            "/panel/portal/interviewer",
            {"student_id": sid, "instance_id": iid} if iid else {"student_id": sid},
        )
        out.append(
            {
                "notification_id": f"interview_booking_pending:{slot.id}",
                "kind": "interview_booking_pending",
                "title_fa": title,
                "summary_fa": summary,
                "action_path": action_path,
                "sort_at": datetime.now(timezone.utc).isoformat(),
                "instance_id": iid,
                "student_id": sid,
            }
        )
    return out


async def build_action_notifications(
    db: AsyncSession,
    user: User,
    *,
    limit: int = 20,
    offset: int = 0,
    process_limit: int = 120,
    scan_cap: int = 600,
) -> dict[str, Any]:
    persisted = await load_active_panel_reminders(db, user.id, limit=50)
    if (user.role or "").strip().lower() == "student":
        r = await db.execute(select(Student).where(Student.user_id == user.id))
        student = r.scalars().first()
        if not student:
            all_items = list(persisted)
            flash_only = await load_panel_flash_messages(db, user.id, limit=100)
            seen_ids = {i.get("notification_id") for i in all_items}
            for f in flash_only:
                if f.get("notification_id") not in seen_ids:
                    all_items.append(f)
            dismissed_ids = await load_dismissed_notification_ids(db, user.id)
            all_items = filter_dismissed_items(all_items, dismissed_ids)
            all_items.sort(key=lambda x: x.get("sort_at") or "", reverse=True)
            total = len(all_items)
            page = all_items[offset : offset + max(limit, 0)]
            return {"items": page, "total": total}
        rows = await _student_pending_notification_sources(db, user, scan_cap=min(scan_cap, 2000))
        all_items: list[dict[str, Any]] = []
        for pi, proc_def, state_def in rows:
            all_items.append(_student_notification_record(student, pi, proc_def, state_def))
    else:
        pl = min(max(process_limit, 1), 200)
        sc = min(max(scan_cap, pl), 2000)
        core = await build_portal_role_process_inbox(
            db,
            portal_role=user.role or "",
            process_limit=pl,
            scan_cap=sc,
            include_assignments_for_staff=(user.role in ("staff", "admin")),
        )
        alerts = await compute_operator_readiness_alerts(db, user)
        merged = _merge_readiness_into_inbox_items(core.get("items") or [], alerts)
        all_items = []
        for raw in merged:
            n = _normalize_raw_to_notification(raw)
            if n:
                all_items.append(n)
        for ib in await _upcoming_paid_interview_slot_notifications(db, user):
            all_items.append(ib)
        for ib in await _pending_payment_interview_slot_notifications(db, user):
            all_items.append(ib)

    if persisted:
        seen_ids = {i.get("notification_id") for i in all_items}
        active_instance_ids = {
            str(i.get("instance_id"))
            for i in all_items
            if i.get("instance_id")
        }
        await prune_stale_task_reminders(
            db,
            user_id=user.id,
            active_instance_ids=active_instance_ids,
        )
        persisted = await load_active_panel_reminders(db, user.id, limit=50)
        for p in persisted:
            pid = p.get("notification_id")
            if pid in seen_ids:
                continue
            p_iid = p.get("instance_id")
            if p_iid and f"process:{p_iid}" in seen_ids:
                continue
            all_items.insert(0, p)

    flash_items = await load_panel_flash_messages(db, user.id, limit=100)
    if flash_items:
        seen_ids = {i.get("notification_id") for i in all_items}
        for f in flash_items:
            if f.get("notification_id") not in seen_ids:
                all_items.append(f)

    dismissed_ids = await load_dismissed_notification_ids(db, user.id)
    all_items = filter_dismissed_items(all_items, dismissed_ids)

    all_items.sort(key=lambda x: x.get("sort_at") or "", reverse=True)
    total = len(all_items)
    page = all_items[offset : offset + max(limit, 0)]
    return {"items": page, "total": total}
