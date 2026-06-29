"""Business logic for process 51 — ta_track_change."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.models.operational_models import Student, User
from app.services.course_committee_roster_service import (
    add_member_to_roster,
    add_track_to_roster,
    ensure_roster_user,
    get_track_by_code,
    list_course_catalog_options,
)

TRACK_LABELS: dict[str, str] = {
    "psychoanalysis_theory_1_5": "تئوری روانکاوی ۱ تا ۵",
    "film_observation_1_3_continuous": "مشاهده فیلم‌های درمانی ۱ تا ۳ و مشاهده مستمر یک درمان تحلیلی",
    "technique_theory_1_3": "تئوری تکنیک‌ها ۱ تا ۳",
    "technique_skills_1_4": "تکنیک: تمرین مهارت‌ها ۱ تا ۴",
    "group_supervision_1_3": "دروس پیشرفته: سوپرویژن گروهی ۱ تا ۳",
    "clinical_case_conference": "دروس پیشرفته: کنفرانس کیس بالینی",
    "early_termination": "دروس پیشرفته: خاتمه زودرس",
    "counter_transference": "دروس پیشرفته: انتقال متقابل",
    "article_writing": "دروس پیشرفته: مقاله‌نویسی",
    "live_therapy_observation": "دروس پیشرفته: مشاهده زنده درمان",
    "live_supervision": "دروس پیشرفته: سوپرویژن زنده",
    "ethics_professional_law_hill": "دروس پیشرفته: کلاس اخلاق و قوانین حرفه‌ای و هیل",
}

TRACK_FIRST_COURSE: dict[str, str] = {
    "psychoanalysis_theory_1_5": "theory_1",
    "film_observation_1_3_continuous": "film_observation_1",
    "technique_theory_1_3": "technique_theory_1",
    "technique_skills_1_4": "technique_skills_1",
    "group_supervision_1_3": "group_supervision_1",
    "clinical_case_conference": "clinical_case_conference",
    "early_termination": "early_termination",
    "counter_transference": "counter_transference",
    "article_writing": "article_writing",
    "live_therapy_observation": "live_therapy_observation",
    "live_supervision": "live_supervision",
    "ethics_professional_law_hill": "ethics_professional_law_hill",
}


def _as_mapping(data: Any) -> dict[str, Any]:
    if isinstance(data, dict):
        return dict(data)
    return {}


def _normalize_tracks(raw: Any) -> list[str]:
    if isinstance(raw, list):
        return [str(x).strip() for x in raw if x is not None and str(x).strip()]
    if raw is not None and str(raw).strip():
        return [str(raw).strip()]
    return []


def track_label_fa(code: str) -> str:
    return TRACK_LABELS.get(str(code), str(code))


def get_active_ta_tracks(student: Student | None) -> list[str]:
    if not student:
        return []
    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    tracks = _normalize_tracks(lms.get("ta_active_tracks"))
    if tracks:
        return tracks
    return _normalize_tracks(extra.get("ta_active_tracks"))


async def build_ta_track_change_context(
    db: AsyncSession,
    student_id: uuid.UUID,
    existing: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """Populate current_tracks and TA name for forms and panels."""
    stmt = select(Student).where(Student.id == student_id)
    student = (await db.execute(stmt)).scalars().first()
    if not student:
        return {}

    extra = _as_mapping(student.extra_data)
    current = get_active_ta_tracks(student)
    user: User | None = None
    if student.user_id:
        user = await db.get(User, student.user_id)

    ctx = {
        "current_tracks": current,
        "current_tracks_labels_fa": [track_label_fa(c) for c in current],
        "ta_name_fa": (user.full_name_fa if user else None) or student.student_code or "",
    }
    merged = {**_as_mapping(existing), **ctx}
    return merged


def validate_new_tracks(
    student: Student | None,
    path: str,
    new_tracks: list[str],
) -> Optional[str]:
    """Return Persian error if validation fails."""
    path_norm = (path or "").strip().lower()
    if path_norm not in ("add", "change"):
        return "مسیر درخواست نامعتبر است."
    selected = _normalize_tracks(new_tracks)
    if not selected:
        return "حداقل یک رسته جدید باید انتخاب شود."

    current = get_active_ta_tracks(student)
    if path_norm == "change":
        if not current:
            return "رسته فعالی در پرونده یافت نشد؛ از مسیر «اضافه کردن رسته» استفاده کنید."
        overlap = [t for t in selected if t in current]
        if overlap:
            labels = "، ".join(track_label_fa(t) for t in overlap)
            return f"رسته(های) انتخابی با رسته فعلی تکراری است: {labels}"
        return None

    overlap = [t for t in selected if t in current]
    if overlap:
        labels = "، ".join(track_label_fa(t) for t in overlap)
        return f"رسته(های) زیر قبلاً در پرونده فعال است و قابل افزودن مجدد نیست: {labels}"
    return None


def ensure_meeting_fields(payload: dict[str, Any], instance_id: uuid.UUID) -> dict[str, Any]:
    """تکمیل لینک جلسه آنلاین در صورت نبود."""
    p = dict(payload or {})
    mode = (p.get("meeting_type") or "").strip()
    if mode == "online" and not (p.get("meeting_link") or "").strip():
        p["meeting_link"] = f"https://meet.anistito.ir/ta-track/{instance_id}"
    if mode == "in_person" and not (p.get("meeting_location_fa") or "").strip():
        p["meeting_location_fa"] = "مکان انستیتو"
    return p


def format_meeting_summary_fa(ctx: dict[str, Any]) -> str:
    parts: list[str] = []
    date = ctx.get("meeting_date")
    time = ctx.get("meeting_time")
    if date or time:
        parts.append(f"تاریخ {date or '—'} ساعت {time or '—'}")
    mode = (ctx.get("meeting_type") or "").strip()
    if mode == "online":
        link = (ctx.get("meeting_link") or "").strip()
        if link:
            parts.append(f"آنلاین — لینک: {link}")
        else:
            parts.append("آنلاین")
    elif mode == "in_person":
        loc = (ctx.get("meeting_location_fa") or "مکان انستیتو").strip()
        parts.append(f"حضوری — {loc}")
    return " | ".join(parts) if parts else ""


async def _resolve_roster_track_code(track_code: str) -> str:
    if get_track_by_code(track_code):
        return track_code
    label = track_label_fa(track_code)
    entry = add_track_to_roster(label, code=track_code)
    return str(entry.get("value") or track_code)


async def _add_ta_to_track_roster(
    db: AsyncSession,
    *,
    track_code: str,
    ta_name: str,
) -> None:
    if not ta_name.strip():
        return
    roster_track = await _resolve_roster_track_code(track_code)
    add_member_to_roster(track=roster_track, kind="teaching_assistant", name_fa=ta_name)
    await ensure_roster_user(
        db,
        track=roster_track,
        kind="teaching_assistant",
        name_fa=ta_name,
    )


def _first_course_label(track_code: str) -> str:
    code = TRACK_FIRST_COURSE.get(track_code)
    if not code:
        return track_label_fa(track_code)
    for opt in list_course_catalog_options():
        if str(opt.get("value")) == code:
            return str(opt.get("label_fa") or code)
    return track_label_fa(track_code)


async def apply_track_change(
    db: AsyncSession,
    student: Student,
    *,
    path: str,
    new_tracks: list[str],
    ta_user: User | None = None,
) -> dict[str, Any]:
    """اعمال تغییر/افزودن رسته در پرونده و چارت."""
    path_norm = (path or "").strip().lower()
    selected = _normalize_tracks(new_tracks)
    err = validate_new_tracks(student, path_norm, selected)
    if err:
        raise ValueError(err)

    extra = _as_mapping(student.extra_data)
    lms = _as_mapping(extra.get("lms"))
    current = get_active_ta_tracks(student)

    if path_norm == "change":
        if current:
            lms["ta_replaced_tracks"] = list(current)
        updated = list(selected)
    else:
        updated = list(dict.fromkeys(current + selected))

    lms["ta_active_tracks"] = updated
    extra["lms"] = lms
    extra["ta_active_tracks"] = updated
    student.extra_data = extra
    flag_modified(student, "extra_data")

    ta_name = ""
    if ta_user:
        ta_name = (ta_user.full_name_fa or "").strip()
    if not ta_name and student.user_id:
        u = await db.get(User, student.user_id)
        ta_name = (u.full_name_fa if u else "") or ""

    if ta_user:
        meta = dict(ta_user.profile_meta or {})
        tracks_meta = list(meta.get("course_committee_tracks") or [])
        for t in selected:
            if t not in tracks_meta:
                tracks_meta.append(t)
        if path_norm == "change" and current:
            tracks_meta = [t for t in tracks_meta if t not in current]
            tracks_meta.extend(selected)
            tracks_meta = list(dict.fromkeys(tracks_meta))
        meta["course_committee_tracks"] = tracks_meta
        ta_user.profile_meta = meta
        flag_modified(ta_user, "profile_meta")

    for track_code in selected:
        await _add_ta_to_track_roster(db, track_code=track_code, ta_name=ta_name)

    course_names = [_first_course_label(t) for t in selected]
    await db.flush()
    return {
        "applied_tracks": updated,
        "new_tracks": selected,
        "path": path_norm,
        "course_names": course_names,
    }
