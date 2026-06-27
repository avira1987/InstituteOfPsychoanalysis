"""فهرست مدرسین و کمک‌مدرسین کمیته دروس — چارت + کاربران سامانه."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import User

MemberKind = Literal["instructor", "teaching_assistant"]

_ROSTER_PATH = Path(__file__).resolve().parents[2] / "metadata" / "course_committee_roster.json"
_roster_cache: dict[str, Any] | None = None


def _load_roster_file() -> dict[str, Any]:
    global _roster_cache
    if _roster_cache is not None:
        return _roster_cache
    with _ROSTER_PATH.open(encoding="utf-8") as f:
        _roster_cache = json.load(f)
    return _roster_cache


def reload_roster_cache() -> None:
    """برای تست — پاک کردن کش فایل چارت."""
    global _roster_cache
    _roster_cache = None


def list_track_options() -> list[dict[str, str]]:
    """گزینه‌های select برای ستون رسته."""
    data = _load_roster_file()
    return [
        {"value": t["code"], "label_fa": t.get("name_fa") or t["code"]}
        for t in data.get("tracks") or []
        if isinstance(t, dict) and t.get("code")
    ]


def get_track_by_code(track_code: str) -> dict[str, Any] | None:
    code = (track_code or "").strip()
    if not code:
        return None
    for t in _load_roster_file().get("tracks") or []:
        if isinstance(t, dict) and t.get("code") == code:
            return t
    return None


def _roster_members_for_track(track: dict[str, Any], kind: MemberKind) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if kind == "instructor":
        edu = track.get("educational_instructor")
        if isinstance(edu, dict) and edu.get("name_fa"):
            out.append(dict(edu))
        for row in track.get("instructors") or []:
            if isinstance(row, dict) and row.get("name_fa"):
                out.append(dict(row))
    else:
        for row in track.get("teaching_assistants") or []:
            if isinstance(row, dict) and row.get("name_fa"):
                out.append(dict(row))
    return out


def _user_matches_track(user: User, track_code: str) -> bool:
    meta = user.profile_meta if isinstance(user.profile_meta, dict) else {}
    tracks = meta.get("course_committee_tracks") or []
    if not isinstance(tracks, list):
        return False
    return track_code in [str(x) for x in tracks]


def _user_member_kind(user: User) -> str | None:
    meta = user.profile_meta if isinstance(user.profile_meta, dict) else {}
    mk = meta.get("member_kind")
    if mk in ("instructor", "teaching_assistant"):
        return mk
    if user.role == "instructor":
        return "instructor"
    if user.role == "teaching_assistant":
        return "teaching_assistant"
    return None


def _option_from_user(user: User) -> dict[str, Any]:
    meta = user.profile_meta if isinstance(user.profile_meta, dict) else {}
    tier = meta.get("tier")
    return {
        "value": str(user.id),
        "label_fa": user.full_name_fa or user.username or str(user.id),
        "tier": tier if isinstance(tier, int) else None,
        "source": "user",
    }


def _option_from_roster_entry(entry: dict[str, Any], user: User | None) -> dict[str, Any]:
    if user is not None:
        opt = _option_from_user(user)
        opt["source"] = "roster+user"
        return opt
    return {
        "value": entry.get("roster_key") or entry.get("name_fa"),
        "label_fa": entry.get("name_fa") or "",
        "tier": entry.get("tier"),
        "source": "roster",
    }


async def list_members(
    db: AsyncSession,
    *,
    track: str,
    kind: MemberKind,
) -> list[dict[str, Any]]:
    """
    ادغام اعضای چارت JSON با کاربران فعال سامانه برای یک رسته.
    value = user_id (UUID) در صورت وجود کاربر؛ در غیر این صورت roster_key.
    """
    track_def = get_track_by_code(track)
    if track_def is None:
        return []

    role_for_kind = "instructor" if kind == "instructor" else "teaching_assistant"
    roster_entries = _roster_members_for_track(track_def, kind)

    # کاربران فعال با نقش و رسته مناسب
    stmt = select(User).where(
        User.is_active.is_(True),
        User.role == role_for_kind,
    )
    result = await db.execute(stmt)
    db_users = [u for u in result.scalars().all() if _user_matches_track(u, track)]

    # نگاشت نام فارسی → کاربر (برای ادغام با چارت)
    by_name: dict[str, User] = {}
    for u in db_users:
        name = (u.full_name_fa or "").strip()
        if name:
            by_name[name] = u

    seen_values: set[str] = set()
    options: list[dict[str, Any]] = []

    for entry in roster_entries:
        name = (entry.get("name_fa") or "").strip()
        matched = by_name.get(name)
        opt = _option_from_roster_entry(entry, matched)
        val = str(opt.get("value") or "")
        if not val or val in seen_values:
            continue
        seen_values.add(val)
        options.append(opt)

    for u in db_users:
        uid = str(u.id)
        if uid in seen_values:
            continue
        if _user_member_kind(u) != kind:
            continue
        seen_values.add(uid)
        options.append(_option_from_user(u))

    options.sort(key=lambda o: (o.get("tier") is None, o.get("tier") or 99, o.get("label_fa") or ""))
    return options


async def resolve_member_label(
    db: AsyncSession,
    *,
    track: str,
    kind: MemberKind,
    value: str,
) -> str | None:
    """برچسب فارسی برای value ذخیره‌شده (user_id یا roster_key یا نام قدیمی)."""
    raw = (value or "").strip()
    if not raw:
        return None

    members = await list_members(db, track=track, kind=kind)
    for m in members:
        if str(m.get("value")) == raw:
            return m.get("label_fa")

    # دادهٔ قدیمی: نام متنی
    try:
        import uuid as _uuid

        uid = _uuid.UUID(raw)
        r = await db.execute(select(User).where(User.id == uid))
        u = r.scalars().first()
        if u and u.full_name_fa:
            return u.full_name_fa
    except (ValueError, TypeError):
        pass

    return raw


async def enrich_course_table_rows(
    db: AsyncSession,
    forms: list,
    values: dict[str, Any],
) -> dict[str, Any]:
    """تبدیل شناسهٔ کاربر به نام نمایشی در ردیف‌های جدول دروس (سازگاری با LMS)."""
    out = dict(values or {})
    for form in forms or []:
        if not isinstance(form, dict):
            continue
        for field in form.get("fields") or []:
            if not isinstance(field, dict) or (field.get("type") or "") != "table":
                continue
            name = field.get("name")
            if not name:
                continue
            rows = out.get(name)
            if not isinstance(rows, list):
                continue
            col_names = {c.get("name") for c in (field.get("columns") or []) if isinstance(c, dict)}
            new_rows = []
            for row in rows:
                if not isinstance(row, dict):
                    new_rows.append(row)
                    continue
                r = dict(row)
                track = str(r.get("track") or "")
                if "course_name" in col_names:
                    raw_name = r.get("course_name")
                    if raw_name:
                        from app.services.course_committee_roster_service import list_course_catalog_options

                        for opt in list_course_catalog_options():
                            if str(opt.get("value")) == str(raw_name):
                                r["course_name"] = opt.get("label_fa") or raw_name
                                break
                if "instructor" in col_names:
                    raw = r.get("instructor_id") or r.get("instructor")
                    if raw:
                        label = await resolve_member_label(
                            db, track=track, kind="instructor", value=str(raw)
                        )
                        if label:
                            r["instructor"] = label
                        if _looks_like_uuid(str(raw)):
                            r["instructor_id"] = str(raw)
                if "teaching_assistant" in col_names:
                    raw = r.get("teaching_assistant_id") or r.get("teaching_assistant")
                    if raw:
                        label = await resolve_member_label(
                            db, track=track, kind="teaching_assistant", value=str(raw)
                        )
                        if label:
                            r["teaching_assistant"] = label
                        if _looks_like_uuid(str(raw)):
                            r["teaching_assistant_id"] = str(raw)
                new_rows.append(r)
            out[name] = new_rows
    return out


def _looks_like_uuid(value: str) -> bool:
    try:
        import uuid as _uuid

        _uuid.UUID(value)
        return True
    except (ValueError, TypeError, AttributeError):
        return False


_CATALOG_PATH = Path(__file__).resolve().parents[2] / "metadata" / "course_catalog.json"
_catalog_cache: dict[str, Any] | None = None


def reload_catalog_cache() -> None:
    global _catalog_cache
    _catalog_cache = None


def _load_catalog_file() -> dict[str, Any]:
    global _catalog_cache
    if _catalog_cache is not None:
        return _catalog_cache
    if not _CATALOG_PATH.is_file():
        _catalog_cache = {"courses": []}
        return _catalog_cache
    with _CATALOG_PATH.open(encoding="utf-8") as f:
        _catalog_cache = json.load(f)
    return _catalog_cache


def _save_catalog_file(data: dict[str, Any]) -> None:
    global _catalog_cache
    with _CATALOG_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _catalog_cache = data


def _save_roster_file(data: dict[str, Any]) -> None:
    global _roster_cache
    with _ROSTER_PATH.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    _roster_cache = data


def _slug_code(prefix: str, label: str) -> str:
    import re

    base = re.sub(r"[^\w]+", "_", label.strip().lower(), flags=re.UNICODE).strip("_")
    if not base:
        base = prefix
    return f"{prefix}_{base}"[:48]


def list_course_catalog_options() -> list[dict[str, str]]:
    data = _load_catalog_file()
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in data.get("courses") or []:
        if not isinstance(row, dict):
            continue
        val = (row.get("value") or row.get("label_fa") or "").strip()
        lab = (row.get("label_fa") or val).strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append({"value": val, "label_fa": lab})
    out.sort(key=lambda o: o.get("label_fa") or "")
    return out


def add_course_to_catalog(label_fa: str) -> dict[str, str]:
    label = (label_fa or "").strip()
    if not label:
        raise ValueError("نام درس خالی است")
    data = _load_catalog_file()
    courses = list(data.get("courses") or [])
    for row in courses:
        if isinstance(row, dict) and (row.get("label_fa") or "").strip() == label:
            return {"value": row.get("value") or label, "label_fa": label}
    value = _slug_code("course", label)
    used = {str(r.get("value")) for r in courses if isinstance(r, dict)}
    if value in used:
        value = f"{value}_{len(used)}"
    opt = {"value": value, "label_fa": label}
    courses.append(opt)
    data["courses"] = courses
    _save_catalog_file(data)
    return opt


def add_track_to_roster(name_fa: str, code: str | None = None) -> dict[str, str]:
    label = (name_fa or "").strip()
    if not label:
        raise ValueError("نام رسته خالی است")
    data = _load_roster_file()
    tracks = list(data.get("tracks") or [])
    for t in tracks:
        if isinstance(t, dict) and (t.get("name_fa") or "").strip() == label:
            return {"value": t["code"], "label_fa": label}
    track_code = (code or "").strip() or _slug_code("track", label)
    used = {str(t.get("code")) for t in tracks if isinstance(t, dict)}
    if track_code in used:
        track_code = f"{track_code}_{len(used)}"
    tracks.append(
        {
            "code": track_code,
            "name_fa": label,
            "instructors": [],
            "teaching_assistants": [],
        }
    )
    data["tracks"] = tracks
    _save_roster_file(data)
    return {"value": track_code, "label_fa": label}


def add_member_to_roster(
    *,
    track: str,
    kind: MemberKind,
    name_fa: str,
) -> dict[str, Any]:
    label = (name_fa or "").strip()
    track_code = (track or "").strip()
    if not label:
        raise ValueError("نام عضو خالی است")
    if not track_code:
        raise ValueError("رسته انتخاب نشده است")
    data = _load_roster_file()
    tracks = data.get("tracks") or []
    track_def = None
    for t in tracks:
        if isinstance(t, dict) and t.get("code") == track_code:
            track_def = t
            break
    if track_def is None:
        raise ValueError("رسته یافت نشد")

    key_field = "instructors" if kind == "instructor" else "teaching_assistants"
    members = list(track_def.get(key_field) or [])
    for row in members:
        if isinstance(row, dict) and (row.get("name_fa") or "").strip() == label:
            return {
                "value": row.get("roster_key") or label,
                "label_fa": label,
                "source": "roster",
            }
    roster_key = _slug_code("inst" if kind == "instructor" else "ta", label)
    used = {str(r.get("roster_key")) for r in members if isinstance(r, dict)}
    if roster_key in used:
        roster_key = f"{roster_key}_{len(used)}"
    entry = {
        "roster_key": roster_key,
        "name_fa": label,
        "tier": 2 if kind == "instructor" else 3,
        "member_kind": kind,
    }
    members.append(entry)
    track_def[key_field] = members
    _save_roster_file(data)
    return {"value": roster_key, "label_fa": label, "source": "roster"}


async def ensure_roster_user(
    db: AsyncSession,
    *,
    track: str,
    kind: MemberKind,
    name_fa: str,
    roster_key: str | None = None,
) -> User:
    """ایجاد کاربر سامانه برای عضو جدید چارت (در صورت نبود)."""
    from app.api.auth import get_password_hash

    label = (name_fa or "").strip()
    track_code = (track or "").strip()
    role = "instructor" if kind == "instructor" else "teaching_assistant"
    rk = (roster_key or _slug_code("inst" if kind == "instructor" else "ta", label)).strip()
    username = f"cc_{track_code}_{rk}"[:80]

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    profile_meta = {
        "course_committee_tracks": [track_code],
        "member_kind": kind,
        "roster_key": rk,
    }
    if user:
        user.full_name_fa = label
        user.role = role
        user.is_active = True
        meta = dict(user.profile_meta or {})
        tracks = list(meta.get("course_committee_tracks") or [])
        if track_code not in tracks:
            tracks.append(track_code)
        meta["course_committee_tracks"] = tracks
        meta["member_kind"] = kind
        meta["roster_key"] = rk
        user.profile_meta = meta
        return user

    user = User(
        id=__import__("uuid").uuid4(),
        username=username,
        email=f"{username}@course-committee.anistito.local",
        hashed_password=get_password_hash("demo123"),
        portal_password_plain="demo123",
        full_name_fa=label,
        role=role,
        is_active=True,
        profile_meta=profile_meta,
    )
    db.add(user)
    await db.flush()
    return user


def _assignment_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            str(row.get("course_name") or ""),
            str(row.get("track") or ""),
            str(row.get("proposed_day") or row.get("day") or ""),
            str(row.get("proposed_time") or row.get("time") or ""),
        ]
    )


async def sync_semester_course_assignments(
    db: AsyncSession,
    *,
    courses_rows: list[dict[str, Any]],
    process_code: str,
    term_label: str | None = None,
) -> int:
    """پس از ثبت لیست دروس، انتساب هر درس را در پروفایل مدرس/کمک‌مدرس ذخیره می‌کند."""
    if not isinstance(courses_rows, list):
        return 0
    updated = 0
    term = term_label or ("پاییز" if "fall" in (process_code or "") else "زمستان" if "winter" in (process_code or "") else "")

    for row in courses_rows:
        if not isinstance(row, dict):
            continue
        course_name = (row.get("course_name") or "").strip()
        if not course_name:
            continue
        track = (row.get("track") or "").strip()
        track_label = track
        track_def = get_track_by_code(track)
        if track_def:
            track_label = track_def.get("name_fa") or track
        payload = {
            "course_name": course_name,
            "track": track,
            "track_label_fa": track_label,
            "day": row.get("proposed_day") or row.get("day") or "",
            "time": row.get("proposed_time") or row.get("time") or "",
            "process_code": process_code,
            "term_label_fa": term,
            "role_kind": None,
        }
        key = _assignment_key(row)

        for kind, id_key, name_key in (
            ("instructor", "instructor_id", "instructor"),
            ("teaching_assistant", "teaching_assistant_id", "teaching_assistant"),
        ):
            raw_id = row.get(id_key)
            raw_name = (row.get(name_key) or "").strip()
            user: User | None = None
            if raw_id and _looks_like_uuid(str(raw_id)):
                user = await db.get(User, __import__("uuid").UUID(str(raw_id)))
            elif raw_name and track:
                members = await list_members(db, track=track, kind=kind)  # type: ignore[arg-type]
                for m in members:
                    if (m.get("label_fa") or "").strip() == raw_name:
                        val = str(m.get("value") or "")
                        if _looks_like_uuid(val):
                            user = await db.get(User, __import__("uuid").UUID(val))
                        break
                if user is None:
                    entry = add_member_to_roster(track=track, kind=kind, name_fa=raw_name)  # type: ignore[arg-type]
                    user = await ensure_roster_user(
                        db,
                        track=track,
                        kind=kind,  # type: ignore[arg-type]
                        name_fa=raw_name,
                        roster_key=entry.get("value"),
                    )
            if not user:
                continue

            meta = dict(user.profile_meta or {})
            assignments = list(meta.get("semester_course_assignments") or [])
            item = {**payload, "role_kind": kind, "assignment_key": key}
            assignments = [a for a in assignments if not (isinstance(a, dict) and a.get("assignment_key") == key and a.get("role_kind") == kind)]
            assignments.append(item)
            meta["semester_course_assignments"] = assignments
            user.profile_meta = meta
            updated += 1

    await db.flush()
    return updated
