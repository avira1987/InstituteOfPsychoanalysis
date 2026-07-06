"""پرونده و سوابق کمک‌مدرسی — تجمیع داده برای UI فرایند ۵۲ (ta_track_completion)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import Student, User
from app.services.course_committee_roster_service import get_track_by_code, list_track_options
from app.services.workflow import _common as C

RANK_LABELS_FA = {
    "teaching_assistant": "کمک مدرس",
    "assistant_faculty": "دستیار هیئت علمی",
    "instructor": "مدرس",
}


def label_rank_fa(rank: str | None) -> str:
    key = (rank or "").strip()
    if not key:
        return "—"
    return RANK_LABELS_FA.get(key, key)


def progress_label_fa(count: int) -> str:
    n = max(0, min(2, int(count)))
    if n >= 2:
        return "۲ از ۲ (تکمیل شده)"
    if n == 1:
        return "۱ از ۲ (در حال انتظار برای بار دوم)"
    return "۰ از ۲ (ثبت‌نام شده، در حال تدریس)"


def role_fa_for_count(count: int) -> str:
    return "مدرس" if int(count) >= 2 else "کمک مدرس"


def _course_catalog_labels() -> dict[str, str]:
    from app.services.course_committee_roster_service import list_course_catalog_options

    return {opt["value"]: opt["label_fa"] for opt in list_course_catalog_options()}


def _track_name(track_code: str) -> str:
    t = get_track_by_code(track_code)
    if t:
        return str(t.get("name_fa") or track_code)
    return track_code


def _assigned_track_codes(extra: dict) -> list[str]:
    portfolio = C.as_mapping(extra.get("ta_portfolio"))
    assigned = portfolio.get("assigned_tracks")
    if isinstance(assigned, list) and assigned:
        return [str(x) for x in assigned if str(x).strip()]

    gb = C.as_mapping(extra.get("gradebook"))
    upgrade = C.as_mapping(gb.get("upgrade_to_ta"))
    tracks = upgrade.get("tracks")
    if isinstance(tracks, list) and tracks:
        return [str(x) for x in tracks if str(x).strip()]

    ta_tracks = extra.get("ta_assigned_tracks")
    if isinstance(ta_tracks, list) and ta_tracks:
        return [str(x) for x in ta_tracks if str(x).strip()]

    return []


def _course_rows_from_portfolio(extra: dict) -> list[dict[str, Any]]:
    portfolio = C.as_mapping(extra.get("ta_portfolio"))
    raw = portfolio.get("courses")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    catalog = _course_catalog_labels()
    for row in raw:
        if not isinstance(row, dict):
            continue
        code = str(row.get("course_code") or row.get("code") or "").strip()
        track_code = str(row.get("track_code") or row.get("track") or "").strip()
        count = int(row.get("successful_ta_count") or row.get("ta_pass_count") or 0)
        name = (
            row.get("course_name_fa")
            or row.get("name_fa")
            or catalog.get(code)
            or code
            or "—"
        )
        out.append({
            "course_code": code,
            "course_name_fa": str(name),
            "track_code": track_code,
            "track_name_fa": str(row.get("track_name_fa") or _track_name(track_code) if track_code else "—"),
            "successful_ta_count": count,
            "progress_fa": progress_label_fa(count),
            "current_role_fa": str(row.get("current_role_fa") or role_fa_for_count(count)),
        })
    return out


def _completed_tracks(extra: dict) -> list[dict[str, Any]]:
    portfolio = C.as_mapping(extra.get("ta_portfolio"))
    raw = portfolio.get("completed_tracks")
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw:
        if isinstance(row, dict):
            code = str(row.get("code") or row.get("track_code") or "").strip()
            out.append({
                "code": code,
                "name_fa": str(row.get("name_fa") or _track_name(code)),
                "completed_at": row.get("completed_at"),
            })
        elif isinstance(row, str) and row.strip():
            code = row.strip()
            out.append({"code": code, "name_fa": _track_name(code), "completed_at": None})
    return out


def _compute_active_tracks(
    assigned: list[str],
    courses: list[dict[str, Any]],
    completed: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    completed_codes = {t["code"] for t in completed if t.get("code")}
    active: list[dict[str, Any]] = []
    track_codes = assigned or [t["value"] for t in list_track_options()]
    for code in track_codes:
        if code in completed_codes:
            continue
        track_courses = [c for c in courses if c.get("track_code") == code]
        if not track_courses and code not in assigned:
            continue
        total = len(track_courses) or 1
        done = sum(1 for c in track_courses if int(c.get("successful_ta_count") or 0) >= 2)
        active.append({
            "code": code,
            "name_fa": _track_name(code),
            "courses_total": total,
            "courses_done": done,
        })
    return active


def build_ta_portfolio(
    student: Student,
    user: User | None = None,
) -> dict[str, Any]:
    """View-model آماده UI از extra_data دانشجو."""
    extra = C.student_extra(student)
    rank = str(extra.get("rank") or "").strip()
    assigned = _assigned_track_codes(extra)
    courses = _course_rows_from_portfolio(extra)
    completed = _completed_tracks(extra)
    active = _compute_active_tracks(assigned, courses, completed)

    name_fa = ""
    if user:
        name_fa = (user.full_name_fa or user.username or "").strip()
    if not name_fa:
        name_fa = student.student_code or ""

    return {
        "student_name_fa": name_fa,
        "rank": rank or None,
        "rank_fa": label_rank_fa(rank),
        "assigned_tracks": assigned,
        "active_tracks": active,
        "completed_tracks": completed,
        "courses": courses,
        "guide_fa": (
            "با رساندن همهٔ دروس یک رسته به «۲ از ۲»، آن رسته به‌صورت خودکار خاتمه می‌یابد "
            "و پیامک تبریک برای شما ارسال می‌شود."
        ),
        "has_ta_data": bool(
            rank in RANK_LABELS_FA
            or assigned
            or courses
            or completed
            or active
        ),
    }


def mark_ta_track_completed(
    student: Student,
    *,
    track_code: str | None = None,
    track_name_fa: str | None = None,
    completed_at: str | None = None,
) -> str:
    """ثبت خاتمه رسته در extra_data.ta_portfolio."""
    code = (track_code or "").strip()
    if not code:
        return "track_code_missing"

    extra = C.student_extra(student)
    portfolio = dict(extra.get("ta_portfolio") or {})
    name = (track_name_fa or "").strip() or _track_name(code)
    ts = completed_at or datetime.now(timezone.utc).isoformat()

    completed = list(portfolio.get("completed_tracks") or [])
    if not any(
        isinstance(r, dict) and (r.get("code") or r.get("track_code")) == code
        for r in completed
    ):
        completed.append({"code": code, "name_fa": name, "completed_at": ts})
    portfolio["completed_tracks"] = completed

    assigned = list(portfolio.get("assigned_tracks") or _assigned_track_codes(extra))
    if code in assigned:
        portfolio["assigned_tracks"] = [c for c in assigned if c != code]
    elif assigned:
        portfolio["assigned_tracks"] = assigned

    portfolio["rank_fa"] = label_rank_fa(str(extra.get("rank") or ""))
    portfolio["last_track_completed_at"] = ts
    portfolio["last_completed_track_code"] = code
    portfolio["last_completed_track_name_fa"] = name

    extra["ta_portfolio"] = portfolio
    C.commit_student_extra(student, extra)
    flag_modified(student, "extra_data")
    return f"track_completed code={code}"


def apply_track_completion_from_context(
    student: Student,
    merged: dict[str, Any],
) -> str:
    track_code = (
        merged.get("track_code")
        or merged.get("completed_track_code")
        or merged.get("track")
    )
    track_name = merged.get("track_name_fa") or merged.get("track_name")
    return mark_ta_track_completed(
        student,
        track_code=str(track_code) if track_code else None,
        track_name_fa=str(track_name) if track_name else None,
    )
