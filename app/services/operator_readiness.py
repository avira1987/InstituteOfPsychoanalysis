"""هشدارهای آمادگی نقش (اسلات مصاحبه، جلسات درمان، …) — برای GET /api/panel/my-operator-followup."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import InterviewSlot, Student, TherapySession, User
from app.services.interview_slot_service import interviewer_capacity_slot_filter

_REPO_ROOT = Path(__file__).resolve().parents[2]
_READINESS_PATH = _REPO_ROOT / "metadata" / "operator_readiness_rules.json"


def _load_readiness_config() -> dict[str, Any]:
    if not _READINESS_PATH.is_file():
        return {"version": "1", "defaults": {}, "rules": []}
    with _READINESS_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _user_label(subject: User) -> str:
    fn = (getattr(subject, "full_name_fa", None) or "").strip()
    if fn:
        return fn
    if subject.username:
        return str(subject.username)
    return str(subject.id)


def _enrich_admin_readiness_alert(alert: dict[str, Any], subject: User, role_label_fa: str) -> dict[str, Any]:
    """هشدار را به نام اپراتور مشخص برچسب می‌زند (برای نمای مدیر)."""
    a = dict(alert)
    label = _user_label(subject)
    rid = str(a.get("id", "alert"))
    a["id"] = f"{rid}:subj:{subject.id}"
    title = a.get("title_fa", "")
    if label and not title.startswith("["):
        a["title_fa"] = f"[{label}] {title}"
    detail = a.get("detail_fa", "")
    a["detail_fa"] = f"اپراتور: {label} ({role_label_fa}) — {detail}"
    meta = dict(a.get("meta") or {})
    meta["subject_user_id"] = str(subject.id)
    meta["subject_username"] = subject.username
    meta["subject_display"] = label
    a["meta"] = meta
    return a


async def _list_users_by_role(db: AsyncSession, role: str, limit: int) -> list[User]:
    stmt = (
        select(User)
        .where(User.role == role, User.is_active.is_(True))
        .order_by(User.username.asc())
        .limit(max(1, limit))
    )
    r = await db.execute(stmt)
    return list(r.scalars().all())


def _session_is_future_scheduled(row: TherapySession, now: datetime, today: date) -> bool:
    if (row.status or "").lower() != "scheduled":
        return False
    if row.session_starts_at is not None:
        st = row.session_starts_at
        if st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)
        return st >= now
    return row.session_date >= today


async def _check_pool_free_slots(
    db: AsyncSession,
    min_count: int,
    ui: dict[str, Any],
    rule_id: str,
) -> list[dict[str, Any]]:
    """اسلات آزاد آینده در استخر عمومی (تعریف‌شده توسط کارمند دفتر)."""
    now = _now_utc()
    q = select(func.count(InterviewSlot.id)).where(
        InterviewSlot.ends_at >= now,
        InterviewSlot.assigned_student_id.is_(None),
    )
    r = await db.execute(q)
    n = int(r.scalar() or 0)
    if n >= min_count:
        return []
    return [
        {
            "id": rule_id,
            "severity": "warning",
            "title_fa": ui.get("title_fa", ""),
            "detail_fa": ui.get("detail_fa", ""),
            "action_label_fa": ui.get("action_label_fa", ""),
            "action_href": ui.get("action_href", ""),
        }
    ]


async def _check_interviewer_free_slots(
    db: AsyncSession,
    user_id: uuid.UUID,
    min_count: int,
    ui: dict[str, Any],
    rule_id: str,
) -> list[dict[str, Any]]:
    """
    اسلات آزاد آیندهٔ قابل رزرو برای دانشجو که این مصاحبه‌گر پوشش می‌دهد:
    اختصاصی (interviewer_user_id) یا استخر اداری بدون مصاحبه‌گر مشخص.
    """
    now = _now_utc()
    q = select(func.count(InterviewSlot.id)).where(
        interviewer_capacity_slot_filter(user_id),
        InterviewSlot.ends_at >= now,
        InterviewSlot.assigned_student_id.is_(None),
    )
    r = await db.execute(q)
    n = int(r.scalar() or 0)
    if n >= min_count:
        return []
    return [
        {
            "id": rule_id,
            "severity": "warning",
            "title_fa": ui.get("title_fa", ""),
            "detail_fa": ui.get("detail_fa", ""),
            "action_label_fa": ui.get("action_label_fa", ""),
            "action_href": ui.get("action_href", ""),
        }
    ]


async def _check_therapist_assigned_sessions(
    db: AsyncSession,
    user_id: uuid.UUID,
    require_therapy_started: bool,
    max_students_scan: int,
    ui: dict[str, Any],
    rule_id: str,
) -> list[dict[str, Any]]:
    now = _now_utc()
    today = now.date()
    stmt = (
        select(Student)
        .where(Student.therapist_id == user_id)
        .order_by(Student.student_code.asc())
        .limit(max(1, min(max_students_scan, 5000)))
    )
    if require_therapy_started:
        stmt = stmt.where(Student.therapy_started.is_(True))

    r = await db.execute(stmt)
    students = list(r.scalars().all())
    if not students:
        return []

    sid_list = [s.id for s in students]
    sess_stmt = select(TherapySession).where(
        TherapySession.therapist_id == user_id,
        TherapySession.student_id.in_(sid_list),
    )
    r_sess = await db.execute(sess_stmt)
    all_sessions = list(r_sess.scalars().all())
    by_student: dict[uuid.UUID, list[TherapySession]] = {}
    for ts in all_sessions:
        by_student.setdefault(ts.student_id, []).append(ts)

    missing: list[Student] = []
    for st in students:
        sessions = by_student.get(st.id, [])
        has_future = any(_session_is_future_scheduled(ts, now, today) for ts in sessions)
        if not has_future:
            missing.append(st)

    if not missing:
        return []

    codes = [s.student_code for s in missing[:8]]
    suffix = ""
    if len(missing) > len(codes):
        suffix = f" و {len(missing) - len(codes)} مورد دیگر"
    codes_txt = "، ".join(codes) + suffix
    base_detail = ui.get("detail_fa", "")
    detail = f"{base_detail} ({len(missing)} نفر: {codes_txt})"

    return [
        {
            "id": rule_id,
            "severity": "warning",
            "title_fa": ui.get("title_fa", ""),
            "detail_fa": detail,
            "action_label_fa": ui.get("action_label_fa", ""),
            "action_href": ui.get("action_href", ""),
            "meta": {"missing_count": len(missing), "sample_student_codes": codes},
        }
    ]


async def _compute_readiness_for_admin(
    db: AsyncSession,
    rules: list[dict[str, Any]],
    defaults: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    برای مدیر سیستم: همان قواعد enabled را برای همهٔ کاربران فعال با نقش مربوط اجرا می‌کند.
    """
    max_ops = int(defaults.get("admin_max_operator_users_per_rule", 400))
    out: list[dict[str, Any]] = []

    for rule in rules:
        check = rule.get("check")
        rule_id = str(rule.get("id") or check or "readiness")
        params = {**defaults, **(rule.get("params") or {})}
        ui = rule.get("ui") or {}

        if check == "interview_pool_free_slots":
            min_count = int(params.get("interview_pool_free_slots", params.get("min_count", 1)))
            # استخر مصاحبه سراسری است — یک هشدار کافی است (نه تکرار برای هر کارمند).
            out.extend(await _check_pool_free_slots(db, min_count, ui, rule_id))

        elif check == "interviewer_min_free_slots":
            min_count = int(params.get("interviewer_min_free_slots", params.get("min_count", 1)))
            for subj in await _list_users_by_role(db, "interviewer", max_ops):
                alerts = await _check_interviewer_free_slots(db, subj.id, min_count, ui, rule_id)
                for a in alerts:
                    out.append(_enrich_admin_readiness_alert(a, subj, "مصاحبه‌گر"))

        elif check == "therapist_future_sessions_for_assigned":
            require_ts = bool(params.get("require_therapy_started", True))
            max_scan = int(params.get("therapist_max_students_scan", params.get("max_students_scan", 2000)))
            for subj in await _list_users_by_role(db, "therapist", max_ops):
                alerts = await _check_therapist_assigned_sessions(
                    db, subj.id, require_ts, max_scan, ui, rule_id
                )
                for a in alerts:
                    out.append(_enrich_admin_readiness_alert(a, subj, "درمانگر"))

    return out


async def _compute_readiness_for_single_user(
    db: AsyncSession,
    user: User,
    role: str,
    rules: list[dict[str, Any]],
    defaults: dict[str, Any],
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    uid = user.id

    for rule in rules:
        roles = rule.get("roles") or []
        if roles and role not in roles:
            continue
        check = rule.get("check")
        rule_id = str(rule.get("id") or check or "readiness")
        params = {**defaults, **(rule.get("params") or {})}
        ui = rule.get("ui") or {}

        if check == "interview_pool_free_slots":
            if role != "staff":
                continue
            min_count = int(params.get("interview_pool_free_slots", params.get("min_count", 1)))
            out.extend(await _check_pool_free_slots(db, min_count, ui, rule_id))
        elif check == "interviewer_min_free_slots":
            if role != "interviewer":
                continue
            min_count = int(params.get("interviewer_min_free_slots", params.get("min_count", 1)))
            out.extend(await _check_interviewer_free_slots(db, uid, min_count, ui, rule_id))
        elif check == "therapist_future_sessions_for_assigned":
            if role != "therapist":
                continue
            require_ts = bool(params.get("require_therapy_started", True))
            max_scan = int(params.get("therapist_max_students_scan", params.get("max_students_scan", 2000)))
            out.extend(
                await _check_therapist_assigned_sessions(
                    db, uid, require_ts, max_scan, ui, rule_id
                )
            )

    return out


async def compute_operator_readiness_alerts(
    db: AsyncSession,
    user: User,
) -> list[dict[str, Any]]:
    """
    هشدارهای آمادگی برای نقش ورود.
    برای admin: تجمیع برای همهٔ مصاحبه‌گران و درمانگران (طبق قواعد JSON).
    """
    role = (user.role or "").strip()
    if role == "student" or not role:
        return []

    cfg = _load_readiness_config()
    defaults = cfg.get("defaults") or {}
    rules = [r for r in (cfg.get("rules") or []) if r.get("enabled") is True]

    if role == "admin":
        return await _compute_readiness_for_admin(db, rules, defaults)

    return await _compute_readiness_for_single_user(db, user, role, rules, defaults)
