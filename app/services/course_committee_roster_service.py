"""فهرست مدرسین و کمک‌مدرسین کمیته دروس — چارت + کاربران سامانه."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import User
from app.core.user_roles import user_has_role

MemberKind = Literal["instructor", "teaching_assistant"]
# نقش نمایشی در ستون «نوع» (شامل مدرس آموزشی)
RosterRoleCode = Literal["instructor", "teaching_assistant", "educational_instructor"]


def _split_roster_kind(kind: str) -> tuple[MemberKind, RosterRoleCode]:
    """kind فرم افزودن عضو → (نقش سامانه، نقش نمایشی چارت)."""
    raw = (kind or "").strip()
    if raw == "educational_instructor":
        return "instructor", "educational_instructor"
    if raw == "teaching_assistant":
        return "teaching_assistant", "teaching_assistant"
    return "instructor", "instructor"


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
    if user_has_role(user, "instructor", admin_bypass=False):
        return "instructor"
    if user_has_role(user, "teaching_assistant", admin_bypass=False):
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
    roster_name = (entry.get("name_fa") or "").strip()
    if user is not None:
        opt = _option_from_user(user)
        opt["source"] = "roster+user"
        # نام چارت برای همگام‌سازی مجوز دروس اولویت دارد
        if roster_name:
            opt["name_fa"] = roster_name
            if not (opt.get("label_fa") or "").strip():
                opt["label_fa"] = roster_name
        return opt
    return {
        "value": entry.get("roster_key") or entry.get("name_fa"),
        "label_fa": roster_name,
        "name_fa": roster_name,
        "tier": entry.get("tier"),
        "source": "roster",
    }


def _attach_auth_fields(
    opt: dict[str, Any],
    *,
    kind: MemberKind,
    entry: dict[str, Any] | None = None,
    user: User | None = None,
) -> dict[str, Any]:
    """مجوز درس را روی گزینهٔ select می‌گذارد؛ تیک چارت و پروفایل با هم ادغام می‌شوند."""
    meta = user.profile_meta if user and isinstance(user.profile_meta, dict) else {}
    opt["authorized_courses"] = _combined_member_grants(entry, user, kind)
    opt["roster_legacy"] = (
        bool(isinstance(entry, dict) and entry.get("roster_legacy") is True)
        or _is_roster_legacy(meta)
        or bool(isinstance(entry, dict) and _is_institutional_roster_entry(entry, kind))
    )
    opt["kind"] = kind
    return opt


def option_authorized_for_course(opt: dict[str, Any], kind: MemberKind, course_value: str) -> bool:
    """آیا این گزینه برای درس داده‌شده قابل انتخاب است؟

    تیک صریح برای درس دیگر = خیر. بدون تیک (عضو چارت رسته) = بله.
    """
    if not course_value:
        return True
    grants = opt.get("authorized_courses") or opt.get(_authorized_courses_key(kind)) or []
    if not grants:
        return True
    return _grants_include_course(grants, course_value)


def _course_refs(course_value: str) -> set[str]:
    """همهٔ ارجاعات ممکن یک درس (کد، برچسب فارسی، نام مستعار)."""
    raw = (course_value or "").strip()
    if not raw:
        return set()
    refs = {raw}
    for row in _load_catalog_file().get("courses") or []:
        if not isinstance(row, dict):
            continue
        val = (row.get("value") or "").strip()
        lab = (row.get("label_fa") or "").strip()
        aliases = row.get("aliases") or []
        alias_list = [str(a).strip() for a in aliases if str(a or "").strip()] if isinstance(aliases, list) else []
        if raw == val or raw == lab or raw in alias_list:
            if val:
                refs.add(val)
            if lab:
                refs.add(lab)
            refs.update(alias_list)
            break
    return refs


def _grants_include_course(grants: Any, course_value: str) -> bool:
    if not grants:
        return False
    refs = _course_refs(course_value)
    if not refs:
        return False
    items = grants if isinstance(grants, list) else [grants]
    for item in items:
        if isinstance(item, str):
            if item in refs or _course_refs(item) & refs:
                return True
            continue
        if not isinstance(item, dict):
            continue
        for key in ("course_code", "course_name", "value", "code"):
            val = (item.get(key) or "").strip()
            if val and (val in refs or bool(_course_refs(val) & refs)):
                return True
    return False


def _authorized_courses_key(kind: MemberKind) -> str:
    return "ta_authorized_courses" if kind == "teaching_assistant" else "instructor_authorized_courses"


def _normalize_grant_list(grants: Any) -> list[str]:
    items = grants if isinstance(grants, list) else ([grants] if grants else [])
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        if isinstance(item, str):
            val = item.strip()
        elif isinstance(item, dict):
            val = str(
                item.get("course_code")
                or item.get("course_name")
                or item.get("value")
                or item.get("code")
                or ""
            ).strip()
        else:
            continue
        if not val or val in seen:
            continue
        seen.add(val)
        out.append(val)
    return out


def _union_grants(*lists: Any) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for lst in lists:
        for val in _normalize_grant_list(lst):
            if val in seen:
                continue
            seen.add(val)
            merged.append(val)
    return merged


def _grants_from_entry(entry: dict[str, Any] | None, kind: MemberKind) -> list[str]:
    if not isinstance(entry, dict):
        return []
    key = _authorized_courses_key(kind)
    return _union_grants(entry.get(key), entry.get("authorized_courses"))


def _grants_from_user(user: User | None, kind: MemberKind) -> list[str]:
    if user is None or not isinstance(user.profile_meta, dict):
        return []
    return _normalize_grant_list(user.profile_meta.get(_authorized_courses_key(kind)))


def _combined_member_grants(
    entry: dict[str, Any] | None,
    user: User | None,
    kind: MemberKind,
) -> list[str]:
    """اجتماع تیک چارت JSON و پروفایل کاربر — هیچ‌کدام دیگری را بازنویسی نمی‌کند."""
    return _union_grants(_grants_from_entry(entry, kind), _grants_from_user(user, kind))


def _write_grants_on_entry(
    entry: dict[str, Any],
    kind: MemberKind,
    courses: list[str] | None,
) -> None:
    """هر دو کلید مجوز درس را با هم می‌نویسد تا UI و JSON یک منبع داشته باشند."""
    if courses is None:
        return
    cleaned = [str(c).strip() for c in courses if str(c or "").strip()]
    entry[_authorized_courses_key(kind)] = list(cleaned)
    entry["authorized_courses"] = list(cleaned)


def _is_institutional_roster_entry(entry: dict[str, Any], kind: MemberKind) -> bool:
    """مدرسین ثابت چارت (بدون محدودیت درس از فرایند ۴۹)."""
    if kind != "instructor":
        return False
    tier = entry.get("tier")
    return isinstance(tier, int) and tier <= 1


def _is_roster_legacy(meta: dict[str, Any] | None) -> bool:
    return isinstance(meta, dict) and meta.get("roster_legacy") is True


def _user_authorized_for_course(user: User, kind: MemberKind, course_value: str) -> bool:
    meta = user.profile_meta if isinstance(user.profile_meta, dict) else {}
    grants = meta.get(_authorized_courses_key(kind)) or []
    return _grants_include_course(grants, course_value)


def _roster_entry_authorized_for_course(
    entry: dict[str, Any],
    kind: MemberKind,
    course_value: str,
    matched_user: User | None,
) -> bool:
    grants = _combined_member_grants(entry, matched_user, kind)
    if not grants:
        # عضو چارت بدون تیک درس — در فهرست رسته قابل انتخاب است
        return True
    return _grants_include_course(grants, course_value)


def merge_course_grants(meta: dict[str, Any], kind: MemberKind, courses: list[str]) -> dict[str, Any]:
    """ادغام دروس مجاز (فرایند ۴۷ برای TA، فرایند ۴۹ برای مدرس)."""
    key = _authorized_courses_key(kind)
    existing = list(meta.get(key) or [])
    seen: set[str] = set()
    merged: list[str] = []
    for item in existing + list(courses or []):
        val = str(item or "").strip()
        if not val or val in seen:
            continue
        seen.add(val)
        merged.append(val)
    meta[key] = merged
    return meta


def _roster_role_for_entry(entry: dict[str, Any], kind: MemberKind) -> tuple[str, str]:
    """کد و برچسب فارسی نقش در چارت: educational_instructor | instructor | teaching_assistant."""
    if kind == "teaching_assistant":
        return "teaching_assistant", "کمک‌مدرس"
    key = str(entry.get("roster_key") or "").strip()
    tier = entry.get("tier")
    if key == "educational_instructor" or tier == 0:
        return "educational_instructor", "مدرس آموزشی"
    return "instructor", "مدرس"


def _member_detail_from_sources(
    entry: dict[str, Any],
    user: User | None,
    *,
    kind: MemberKind,
    track: str,
) -> dict[str, Any]:
    """جزئیات عضو برای پنل مدیریت چارت."""
    meta = user.profile_meta if user and isinstance(user.profile_meta, dict) else {}
    roster_legacy = (
        entry.get("roster_legacy") is True
        or _is_roster_legacy(meta)
        or _is_institutional_roster_entry(entry, kind)
    )
    opt = _option_from_roster_entry(entry, user)
    name_fa = (
        (opt.get("name_fa") or "").strip()
        or (entry.get("name_fa") or "").strip()
        or (opt.get("label_fa") or "").strip()
    )
    role_code, role_label_fa = _roster_role_for_entry(entry, kind)
    courses = _combined_member_grants(entry, user, kind)
    return {
        **opt,
        "kind": kind,
        "track": track,
        "name_fa": name_fa,
        "label_fa": (opt.get("label_fa") or name_fa),
        "user_id": str(user.id) if user else None,
        "roster_key": entry.get("roster_key"),
        "roster_legacy": roster_legacy,
        "authorized_courses": courses,
        "course_count": len(courses),
        "role_code": role_code,
        "role_label_fa": role_label_fa,
        "tier": entry.get("tier") if entry.get("tier") is not None else meta.get("tier"),
    }


async def list_members(
    db: AsyncSession,
    *,
    track: str,
    kind: MemberKind,
    course: str | None = None,
    include_all: bool = False,
) -> list[dict[str, Any]]:
    """
    ادغام اعضای چارت JSON با کاربران فعال سامانه برای یک رسته.
    value = user_id (UUID) در صورت وجود کاربر؛ در غیر این صورت roster_key.
    اگر course داده شود، فقط اعضای مجاز برای آن درس (فرایند ۴۷/۴۹) برگردانده می‌شوند.
    با include_all=True فیلتر درس نادیده گرفته می‌شود (پنل مدیریت چارت).
    """
    track_code = resolve_track_code(track) or (track or "").strip()
    track_def = get_track_by_code(track_code)
    if track_def is None:
        return []

    course_filter = None if include_all else ((course or "").strip() or None)
    role_for_kind = "instructor" if kind == "instructor" else "teaching_assistant"
    roster_entries = _roster_members_for_track(track_def, kind)

    stmt = select(User).where(
        User.is_active.is_(True),
        User.role == role_for_kind,
    )
    result = await db.execute(stmt)
    db_users = [u for u in result.scalars().all() if _user_matches_track(u, track_code)]

    by_name: dict[str, User] = {}
    for u in db_users:
        name = (u.full_name_fa or "").strip()
        if name:
            by_name[_normalize_fa(name)] = u

    seen_values: set[str] = set()
    options: list[dict[str, Any]] = []

    for entry in roster_entries:
        name = (entry.get("name_fa") or "").strip()
        matched = by_name.get(_normalize_fa(name)) if name else None
        if course_filter and not _roster_entry_authorized_for_course(
            entry, kind, course_filter, matched
        ):
            continue
        opt = _attach_auth_fields(
            _option_from_roster_entry(entry, matched),
            kind=kind,
            entry=entry,
            user=matched,
        )
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
        if course_filter and not _user_authorized_for_course(u, kind, course_filter):
            continue
        seen_values.add(uid)
        options.append(_attach_auth_fields(_option_from_user(u), kind=kind, user=u))

    options.sort(key=lambda o: (o.get("tier") is None, o.get("tier") or 99, o.get("label_fa") or ""))
    return options


async def list_track_roster_detail(
    db: AsyncSession,
    *,
    track: str,
) -> dict[str, list[dict[str, Any]]]:
    """فهرست کامل مدرسین و کمک‌مدرسین یک رسته برای پنل مدیریت."""
    track_def = get_track_by_code(track)
    if track_def is None:
        return {"instructors": [], "teaching_assistants": []}

    track_code = (track or "").strip()
    out: dict[str, list[dict[str, Any]]] = {"instructors": [], "teaching_assistants": []}

    for kind, key in (("instructor", "instructors"), ("teaching_assistant", "teaching_assistants")):
        roster_entries = _roster_members_for_track(track_def, kind)  # type: ignore[arg-type]
        role_for_kind = "instructor" if kind == "instructor" else "teaching_assistant"
        stmt = select(User).where(User.is_active.is_(True), User.role == role_for_kind)
        result = await db.execute(stmt)
        db_users = [u for u in result.scalars().all() if _user_matches_track(u, track_code)]
        by_name: dict[str, User] = {}
        for u in db_users:
            name = (u.full_name_fa or "").strip()
            if name:
                by_name[_normalize_fa(name)] = u

        seen_names: set[str] = set()
        items: list[dict[str, Any]] = []
        for entry in roster_entries:
            name = (entry.get("name_fa") or "").strip()
            if not name:
                continue
            norm = _normalize_fa(name)
            if norm in seen_names:
                continue
            seen_names.add(norm)
            matched = by_name.get(norm)
            items.append(
                _member_detail_from_sources(entry, matched, kind=kind, track=track_code)  # type: ignore[arg-type]
            )

        for u in db_users:
            name = (u.full_name_fa or "").strip()
            if not name:
                continue
            norm = _normalize_fa(name)
            if norm in seen_names:
                continue
            if _user_member_kind(u) != kind:
                continue
            seen_names.add(norm)
            entry = {
                "roster_key": (u.profile_meta or {}).get("roster_key"),
                "name_fa": name,
                "tier": (u.profile_meta or {}).get("tier"),
                "member_kind": kind,
            }
            items.append(
                _member_detail_from_sources(entry, u, kind=kind, track=track_code)  # type: ignore[arg-type]
            )

        items.sort(key=lambda o: (o.get("tier") is None, o.get("tier") or 99, o.get("label_fa") or ""))
        out[key] = items

    return out


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
    """تبدیل شناسهٔ کاربر و کدهای فنی به نام نمایشی فارسی در ردیف‌های جدول دروس."""
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
                if "course_name" in col_names:
                    raw_name = r.get("course_name")
                    if raw_name:
                        label, code = _course_label_and_code(str(raw_name))
                        if label:
                            r["course_name"] = label
                        if code and code != label:
                            r["course_code"] = code
                        if "track" in col_names and not (r.get("track") or "").strip():
                            resolved = resolve_track_for_course(str(raw_name))
                            if resolved:
                                r["track_code"] = resolved
                                r["track"] = resolve_track_display_fa(resolved)
                if "track" in col_names:
                    raw_track = str(r.get("track") or "").strip()
                    if raw_track:
                        code = resolve_track_code(raw_track) or str(r.get("track_code") or "").strip()
                        if code:
                            r["track_code"] = code
                        r["track"] = resolve_track_display_fa(raw_track)
                track_for_lookup = (
                    str(r.get("track_code") or "").strip()
                    or resolve_track_code(str(r.get("track") or ""))
                    or ""
                )
                if "instructor" in col_names:
                    raw = r.get("instructor_id") or r.get("instructor")
                    if raw:
                        label = await resolve_member_label(
                            db, track=track_for_lookup, kind="instructor", value=str(raw)
                        )
                        if label:
                            r["instructor"] = _normalize_fa(label)
                        if _looks_like_uuid(str(raw)):
                            r["instructor_id"] = str(raw)
                if "teaching_assistant" in col_names:
                    raw = r.get("teaching_assistant_id") or r.get("teaching_assistant")
                    if raw:
                        label = await resolve_member_label(
                            db, track=track_for_lookup, kind="teaching_assistant", value=str(raw)
                        )
                        if label:
                            r["teaching_assistant"] = _normalize_fa(label)
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


def _normalize_catalog_name(name: str) -> str:
    return (name or "").strip().replace("ي", "ی").replace("ك", "ک")


_CATALOG_DIGIT_TABLE = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")
_CATALOG_WORD_NUMBERS = (
    (r"(?<!\S)یک(?!\S)", "1"),
    (r"(?<!\S)دو(?!\S)", "2"),
    (r"(?<!\S)سه(?!\S)", "3"),
    (r"(?<!\S)چهار(?!\S)", "4"),
    (r"(?<!\S)پنج(?!\S)", "5"),
)


def _fold_catalog_name(name: str) -> str:
    """Normalize labels so «تئوری تکنیک یک» matches catalog «تئوری تکنیک‌ها ۱»."""
    s = _normalize_catalog_name(name).translate(_CATALOG_DIGIT_TABLE)
    s = s.replace("تکنیک‌ها", "تکنیک").replace("تکنیکها", "تکنیک")
    s = s.replace("‌", " ").replace("ـ", " ")
    s = re.sub(r"[()\[\]«»]", " ", s)
    for pattern, repl in _CATALOG_WORD_NUMBERS:
        s = re.sub(pattern, repl, s)
    return re.sub(r"\s+", " ", s).strip()


def get_catalog_course(code_or_name: str) -> dict[str, Any] | None:
    """Find a catalog row by value, Persian label, or SOP alias."""
    raw = _normalize_catalog_name(code_or_name)
    if not raw:
        return None
    folded = _fold_catalog_name(raw)
    for row in _load_catalog_file().get("courses") or []:
        if not isinstance(row, dict):
            continue
        val = _normalize_catalog_name(str(row.get("value") or ""))
        lab = _normalize_catalog_name(str(row.get("label_fa") or ""))
        names = [val, lab]
        aliases = row.get("aliases") or []
        if isinstance(aliases, list):
            names.extend(_normalize_catalog_name(str(a)) for a in aliases if str(a).strip())
        if raw in names or folded in {_fold_catalog_name(n) for n in names if n}:
            return row
    return None


def list_course_catalog_options() -> list[dict[str, Any]]:
    data = _load_catalog_file()
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in data.get("courses") or []:
        if not isinstance(row, dict):
            continue
        val = (row.get("value") or row.get("label_fa") or "").strip()
        if not val or val in seen:
            continue
        seen.add(val)
        out.append(_course_row_to_option(row))
    out.sort(
        key=lambda o: (
            int(o.get("curriculum_term") or 99),
            o.get("program_kind") or "",
            o.get("label_fa") or "",
        )
    )
    return out


KNOWN_SYSTEM_PREREQUISITE_CODES = (
    "internship_started",
    "clinical_hours_500",
    "individual_supervision_50h",
    "individual_supervision_100h",
)


def list_system_prerequisites() -> list[dict[str, Any]]:
    """رجیستری پیش‌نیاز سیستمی کاتالوگ (یادآور؛ enforced فعلاً false است)."""
    data = _load_catalog_file()
    raw = data.get("system_prerequisites")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip()
            if not code or code in seen:
                continue
            seen.add(code)
            row: dict[str, Any] = {
                "code": code,
                "label_fa": str(item.get("label_fa") or code).strip() or code,
                "enforced": bool(item.get("enforced")),
            }
            hint = str(item.get("activation_hint_fa") or "").strip()
            if hint:
                row["activation_hint_fa"] = hint
            out.append(row)
    if not out:
        for code in KNOWN_SYSTEM_PREREQUISITE_CODES:
            out.append({"code": code, "label_fa": code, "enforced": False})
    return out


def catalog_units_for_course(code_or_name: str, default: int = 1) -> int:
    """SOP unit count for a course; default 1 when unknown."""
    row = get_catalog_course(code_or_name)
    if not row:
        return default
    try:
        units = int(row.get("units") or default)
    except (TypeError, ValueError):
        return default
    return units if units > 0 else default


def build_sop_curriculum_draft_rows(curriculum_term: int) -> list[dict[str, Any]]:
    """ردیف‌های جدول لیست دروس از کاتالوگ SOP برای یک ترم برنامه (۱–۸)."""
    try:
        term = int(curriculum_term)
    except (TypeError, ValueError):
        return []
    if term < 1 or term > 8:
        return []
    rows: list[dict[str, Any]] = []
    for opt in list_course_catalog_options():
        if not isinstance(opt, dict):
            continue
        try:
            opt_term = int(opt.get("curriculum_term") or 0)
        except (TypeError, ValueError):
            continue
        if opt_term != term:
            continue
        course_code = str(opt.get("value") or "").strip()
        course_label = str(opt.get("label_fa") or course_code).strip()
        if not course_label:
            continue
        track_code = str(opt.get("track") or "").strip()
        track_label = resolve_track_display_fa(track_code) if track_code else ""
        row: dict[str, Any] = {
            "course_name": course_label,
            "proposed_day": "",
            "proposed_time": "",
            "instructor": "",
            "teaching_assistant": "",
            "track": track_label or track_code,
        }
        if course_code:
            row["course_code"] = course_code
        if track_code:
            row["track_code"] = track_code
        if opt.get("units") not in (None, ""):
            try:
                units = int(opt["units"])
                if units > 0:
                    row["units"] = units
            except (TypeError, ValueError):
                pass
        rows.append(row)
    rows.sort(key=lambda r: (r.get("track") or "", r.get("course_name") or ""))
    return rows


def resolve_track_for_course(course_value: str) -> str | None:
    """نگاشت نام/کد درس به کد رسته از course_catalog.json."""
    row = get_catalog_course(course_value)
    if not row:
        return None
    track = (row.get("track") or "").strip()
    return track or None


def add_course_to_catalog(
    label_fa: str,
    track: str | None = None,
    **curriculum: Any,
) -> dict[str, Any]:
    label = (label_fa or "").strip()
    if not label:
        raise ValueError("نام درس خالی است")
    track_code = (track or "").strip()
    if not track_code:
        raise ValueError("انتخاب رسته الزامی است")
    if get_track_by_code(track_code) is None:
        raise ValueError("رسته انتخاب‌شده در فهرست رسته‌های موجود نیست")
    extra = _curriculum_payload(curriculum)
    data = _load_catalog_file()
    courses = list(data.get("courses") or [])
    for row in courses:
        if isinstance(row, dict) and (row.get("label_fa") or "").strip() == label:
            existing_track = (row.get("track") or "").strip()
            if existing_track and existing_track != track_code:
                raise ValueError("این درس قبلاً با رسته دیگری ثبت شده است")
            if not existing_track:
                row["track"] = track_code
            _apply_curriculum_fields(row, extra)
            data["courses"] = courses
            _save_catalog_file(data)
            return _course_row_to_option(row)
    value = _slug_code("course", label)
    used = {str(r.get("value")) for r in courses if isinstance(r, dict)}
    if value in used:
        value = f"{value}_{len(used)}"
    opt: dict[str, Any] = {"value": value, "label_fa": label, "track": track_code}
    _apply_curriculum_fields(opt, extra)
    courses.append(opt)
    data["courses"] = courses
    _save_catalog_file(data)
    return _course_row_to_option(opt)


def _curriculum_payload(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if "units" in raw and raw["units"] is not None:
        try:
            units = int(raw["units"])
        except (TypeError, ValueError) as exc:
            raise ValueError("تعداد واحد نامعتبر است") from exc
        if units < 1:
            raise ValueError("تعداد واحد باید حداقل ۱ باشد")
        out["units"] = units
    if "curriculum_term" in raw and raw["curriculum_term"] is not None:
        try:
            term = int(raw["curriculum_term"])
        except (TypeError, ValueError) as exc:
            raise ValueError("شماره ترم نامعتبر است") from exc
        if term < 1 or term > 8:
            raise ValueError("شماره ترم باید بین ۱ و ۸ باشد")
        out["curriculum_term"] = term
    if "program_kind" in raw and raw["program_kind"] is not None:
        kind = str(raw["program_kind"]).strip()
        if kind and kind not in {"introductory", "comprehensive"}:
            raise ValueError("نوع دوره باید آشنایی یا جامع باشد")
        if kind:
            out["program_kind"] = kind
    if "class_hours" in raw and raw["class_hours"] is not None:
        out["class_hours"] = str(raw["class_hours"]).strip()
    if "retake_exam" in raw and raw["retake_exam"] is not None:
        out["retake_exam"] = bool(raw["retake_exam"])
    if "evaluation_fa" in raw and raw["evaluation_fa"] is not None:
        out["evaluation_fa"] = str(raw["evaluation_fa"]).strip()
    if "prerequisite_codes" in raw and raw["prerequisite_codes"] is not None:
        codes = raw["prerequisite_codes"]
        if not isinstance(codes, list):
            raise ValueError("پیش‌نیاز باید فهرست کد درس باشد")
        out["prerequisite_codes"] = [str(c).strip() for c in codes if str(c).strip()]
    if "system_prerequisite_codes" in raw and raw["system_prerequisite_codes"] is not None:
        codes = raw["system_prerequisite_codes"]
        if not isinstance(codes, list):
            raise ValueError("پیش‌نیاز سیستمی باید فهرست کد باشد")
        out["system_prerequisite_codes"] = [str(c).strip() for c in codes if str(c).strip()]
    if "prerequisite_notes" in raw and raw["prerequisite_notes"] is not None:
        out["prerequisite_notes"] = str(raw["prerequisite_notes"]).strip()
    if "single_course_allowed" in raw and raw["single_course_allowed"] is not None:
        out["single_course_allowed"] = bool(raw["single_course_allowed"])
    if "subtitle_fa" in raw and raw["subtitle_fa"] is not None:
        out["subtitle_fa"] = str(raw["subtitle_fa"]).strip()
    return out


def _apply_curriculum_fields(row: dict[str, Any], extra: dict[str, Any]) -> None:
    for key, value in extra.items():
        row[key] = value


def _course_row_to_option(row: dict[str, Any]) -> dict[str, Any]:
    value = str(row.get("value") or row.get("label_fa") or "").strip()
    label = str(row.get("label_fa") or value).strip()
    out: dict[str, Any] = {"value": value, "label_fa": label}
    track = str(row.get("track") or "").strip()
    if track:
        out["track"] = track
    subtitle = str(row.get("subtitle_fa") or "").strip()
    if subtitle:
        out["subtitle_fa"] = subtitle
    if row.get("units") not in (None, ""):
        try:
            out["units"] = int(row["units"])
        except (TypeError, ValueError):
            pass
    if row.get("curriculum_term") not in (None, ""):
        try:
            out["curriculum_term"] = int(row["curriculum_term"])
        except (TypeError, ValueError):
            pass
    kind = str(row.get("program_kind") or "").strip()
    if kind:
        out["program_kind"] = kind
    hours = str(row.get("class_hours") or "").strip()
    if hours:
        out["class_hours"] = hours
    if "retake_exam" in row and row.get("retake_exam") is not None:
        out["retake_exam"] = bool(row.get("retake_exam"))
    evaluation = str(row.get("evaluation_fa") or "").strip()
    if evaluation:
        out["evaluation_fa"] = evaluation
    prereqs = row.get("prerequisite_codes")
    if isinstance(prereqs, list):
        out["prerequisite_codes"] = [str(c).strip() for c in prereqs if str(c).strip()]
    sys_prereqs = row.get("system_prerequisite_codes")
    if isinstance(sys_prereqs, list):
        out["system_prerequisite_codes"] = [
            str(c).strip() for c in sys_prereqs if str(c).strip()
        ]
    notes = str(row.get("prerequisite_notes") or "").strip()
    if notes:
        out["prerequisite_notes"] = notes
    if row.get("single_course_allowed") is not None:
        out["single_course_allowed"] = bool(row.get("single_course_allowed"))
    aliases = row.get("aliases")
    if isinstance(aliases, list) and aliases:
        out["aliases"] = [str(a).strip() for a in aliases if str(a).strip()]
    return out


def update_course_in_catalog(
    course_value: str,
    *,
    name_fa: str | None = None,
    track: str | None = None,
    **curriculum: Any,
) -> dict[str, Any]:
    """ویرایش نام، رسته یا مشخصات واحد/ترم یک درس در کاتالوگ."""
    code = (course_value or "").strip()
    if not code:
        raise ValueError("کد درس خالی است")
    extra = _curriculum_payload(curriculum)
    new_label = (name_fa or "").strip() if name_fa is not None else None
    new_track = (track or "").strip() if track is not None else None
    if new_label is None and new_track is None and not extra:
        raise ValueError("هیچ فیلدی برای ویرایش ارسال نشده است")
    if new_label is not None and not new_label:
        raise ValueError("نام درس خالی است")
    if new_track is not None:
        if not new_track:
            raise ValueError("انتخاب رسته الزامی است")
        if get_track_by_code(new_track) is None:
            raise ValueError("رسته انتخاب‌شده در فهرست رسته‌های موجود نیست")

    data = _load_catalog_file()
    courses = list(data.get("courses") or [])
    target: dict[str, Any] | None = None
    for row in courses:
        if not isinstance(row, dict):
            continue
        val = str(row.get("value") or "").strip()
        if val == code:
            target = row
            break
    if target is None:
        raise ValueError("درس در کاتالوگ یافت نشد")

    if new_label is not None:
        for row in courses:
            if row is target or not isinstance(row, dict):
                continue
            if (row.get("label_fa") or "").strip() == new_label:
                raise ValueError("درس دیگری با این نام وجود دارد")
        target["label_fa"] = new_label
    if new_track is not None:
        target["track"] = new_track
    _apply_curriculum_fields(target, extra)

    data["courses"] = courses
    _save_catalog_file(data)
    return _course_row_to_option(target)


def remove_course_from_catalog(course_value: str) -> bool:
    """حذف درس از کاتالوگ و پاک‌سازی ارجاع در مجوزهای چارت JSON."""
    code = (course_value or "").strip()
    if not code:
        return False
    data = _load_catalog_file()
    courses = list(data.get("courses") or [])
    filtered: list[Any] = []
    removed = False
    for row in courses:
        if not isinstance(row, dict):
            filtered.append(row)
            continue
        val = str(row.get("value") or "").strip()
        if val == code:
            removed = True
            continue
        filtered.append(row)
    if not removed:
        return False
    data["courses"] = filtered
    _save_catalog_file(data)
    _scrub_course_from_roster_grants(code)
    return True


def _scrub_course_from_roster_grants(course_value: str) -> None:
    code = (course_value or "").strip()
    if not code:
        return
    data = _load_roster_file()
    changed = False
    grant_keys = ("authorized_courses", "instructor_authorized_courses", "ta_authorized_courses")
    for track in data.get("tracks") or []:
        if not isinstance(track, dict):
            continue
        for kind_key in ("instructors", "teaching_assistants"):
            members = track.get(kind_key) or []
            if not isinstance(members, list):
                continue
            for member in members:
                if not isinstance(member, dict):
                    continue
                for gk in grant_keys:
                    grants = member.get(gk)
                    if not isinstance(grants, list):
                        continue
                    cleaned = [g for g in grants if str(g).strip() != code]
                    if len(cleaned) != len(grants):
                        member[gk] = cleaned
                        changed = True
    if changed:
        _save_roster_file(data)


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


def update_track_in_roster(track_code: str, name_fa: str) -> dict[str, str]:
    """تغییر نام رسته؛ کد ثابت می‌ماند تا درس‌ها و اعضای چارت قطع نشوند."""
    code = (track_code or "").strip()
    label = (name_fa or "").strip()
    if not code:
        raise ValueError("کد رسته خالی است")
    if not label:
        raise ValueError("نام رسته خالی است")
    data = _load_roster_file()
    tracks = list(data.get("tracks") or [])
    target: dict[str, Any] | None = None
    for t in tracks:
        if isinstance(t, dict) and t.get("code") == code:
            target = t
            break
    if target is None:
        raise ValueError("رسته یافت نشد")
    label_norm = _normalize_fa(label)
    for t in tracks:
        if not isinstance(t, dict) or t.get("code") == code:
            continue
        other = (t.get("name_fa") or "").strip()
        if other == label or _normalize_fa(other) == label_norm:
            raise ValueError("رسته‌ای با این نام از قبل وجود دارد")
    target["name_fa"] = label
    data["tracks"] = tracks
    _save_roster_file(data)
    return {"value": code, "label_fa": label}


def remove_track_from_roster(track_code: str) -> bool:
    """حذف رسته خالی؛ اگر عضو یا درس وابسته داشته باشد خطا می‌دهد."""
    code = (track_code or "").strip()
    if not code:
        raise ValueError("کد رسته خالی است")
    track_def = get_track_by_code(code)
    if track_def is None:
        return False

    instructors = list(track_def.get("instructors") or [])
    tas = list(track_def.get("teaching_assistants") or [])
    edu = track_def.get("educational_instructor")
    has_edu = isinstance(edu, dict) and bool((edu.get("name_fa") or "").strip())
    if instructors or tas or has_edu:
        raise ValueError("ابتدا همهٔ مدرسین و کمک‌مدرسین این رسته را حذف کنید")

    linked_courses = [
        c for c in list_course_catalog_options() if (c.get("track") or "").strip() == code
    ]
    if linked_courses:
        raise ValueError(
            f"این رسته به {len(linked_courses)} درس در کاتالوگ متصل است — ابتدا درس‌ها را حذف یا جابه‌جا کنید"
        )

    data = _load_roster_file()
    tracks = list(data.get("tracks") or [])
    filtered = [t for t in tracks if not (isinstance(t, dict) and t.get("code") == code)]
    if len(filtered) == len(tracks):
        return False
    data["tracks"] = filtered
    _save_roster_file(data)
    return True


def _roster_names_match(left: str, right: str) -> bool:
    a = (left or "").strip()
    b = (right or "").strip()
    if not a or not b:
        return False
    return a == b or _normalize_fa(a) == _normalize_fa(b)


def _member_entry_matches(
    row: Any,
    *,
    name_fa: str,
    roster_key: str | None = None,
) -> bool:
    if not isinstance(row, dict):
        return False
    key = (roster_key or "").strip()
    if key and (row.get("roster_key") or "").strip() == key:
        return True
    return _roster_names_match(row.get("name_fa") or "", name_fa)


def _extract_member_entry_from_track(
    track_def: dict[str, Any],
    *,
    name_fa: str,
    kind: MemberKind | None = None,
    roster_key: str | None = None,
) -> dict[str, Any] | None:
    """برداشتن ردیف عضو از چارت (مدرس آموزشی / مدرسین / کمک‌مدرسین) و برگرداندن کپی آن."""
    label = (name_fa or "").strip()
    key = (roster_key or "").strip() or None
    if not label and not key:
        return None

    if kind in (None, "instructor"):
        edu = track_def.get("educational_instructor")
        if _member_entry_matches(edu, name_fa=label, roster_key=key):
            track_def["educational_instructor"] = None
            return dict(edu)

    if kind in (None, "instructor"):
        members = list(track_def.get("instructors") or [])
        kept: list[Any] = []
        found: dict[str, Any] | None = None
        for row in members:
            if found is None and _member_entry_matches(row, name_fa=label, roster_key=key):
                found = dict(row)
                continue
            kept.append(row)
        if found is not None:
            track_def["instructors"] = kept
            return found

    if kind in (None, "teaching_assistant"):
        members = list(track_def.get("teaching_assistants") or [])
        kept = []
        found = None
        for row in members:
            if found is None and _member_entry_matches(row, name_fa=label, roster_key=key):
                found = dict(row)
                continue
            kept.append(row)
        if found is not None:
            track_def["teaching_assistants"] = kept
            return found

    return None


def remove_member_from_roster(
    *,
    track: str,
    kind: MemberKind,
    name_fa: str,
    roster_key: str | None = None,
) -> bool:
    """حذف عضو از چارت JSON بر اساس نام فارسی یا کلید چارت."""
    label = (name_fa or "").strip()
    key = (roster_key or "").strip() or None
    track_code = resolve_track_code(track) or (track or "").strip()
    if (not label and not key) or not track_code:
        return False
    data = _load_roster_file()
    track_def = None
    for t in data.get("tracks") or []:
        if isinstance(t, dict) and t.get("code") == track_code:
            track_def = t
            break
    if track_def is None:
        return False

    extracted = None
    for _ in range(8):
        hit = _extract_member_entry_from_track(
            track_def, name_fa=label, kind=kind, roster_key=key,
        )
        if hit is None:
            break
        extracted = hit
        # بعد از اولین حذف، فقط با نام ادامه بده تا ردیف تکراری با کلید دیگر هم پاک شود
        key = None
    if extracted is None:
        return False
    _save_roster_file(data)
    return True


async def delete_roster_member(
    db: AsyncSession,
    *,
    track: str,
    kind: MemberKind,
    name_fa: str = "",
    user_id: Any | None = None,
    roster_key: str | None = None,
) -> bool:
    """حذف از چارت JSON و جدا کردن کاربر متصل — حتی اگر آخرین عضو رسته باشد."""
    import uuid as _uuid

    from sqlalchemy.orm.attributes import flag_modified

    label = (name_fa or "").strip()
    key = (roster_key or "").strip() or None
    track_code = resolve_track_code(track) or (track or "").strip()
    if not track_code:
        return False

    user: User | None = None
    if user_id is not None:
        try:
            uid = user_id if isinstance(user_id, _uuid.UUID) else _uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            uid = None
        if uid is not None:
            user = await db.get(User, uid)

    if user is not None:
        if not label:
            label = (user.full_name_fa or user.username or "").strip()
        if not key:
            meta = user.profile_meta if isinstance(user.profile_meta, dict) else {}
            key = str(meta.get("roster_key") or "").strip() or None

    json_removed = remove_member_from_roster(
        track=track_code, kind=kind, name_fa=label, roster_key=key,
    )
    if user is not None and not json_removed:
        user_key = None
        meta = user.profile_meta if isinstance(user.profile_meta, dict) else {}
        user_key = str(meta.get("roster_key") or "").strip() or None
        json_removed = remove_member_from_roster(
            track=track_code,
            kind=kind,
            name_fa=(user.full_name_fa or label),
            roster_key=user_key,
        )

    candidates: list[User] = []
    seen_ids: set[Any] = set()
    if user is not None:
        candidates.append(user)
        seen_ids.add(user.id)

    result = await db.execute(select(User).where(User.is_active.is_(True)))
    for u in result.scalars().all():
        if u.id in seen_ids:
            continue
        if not _user_matches_track(u, track_code):
            continue
        meta = u.profile_meta if isinstance(u.profile_meta, dict) else {}
        name_hit = bool(label) and _roster_names_match(u.full_name_fa or "", label)
        key_hit = bool(key) and str(meta.get("roster_key") or "").strip() == key
        if name_hit or key_hit:
            candidates.append(u)
            seen_ids.add(u.id)

    unlinked = False
    for u in candidates:
        meta = dict(u.profile_meta or {})
        tracks = [str(t) for t in (meta.get("course_committee_tracks") or [])]
        if track_code not in tracks:
            continue
        meta["course_committee_tracks"] = [t for t in tracks if t != track_code]
        u.profile_meta = meta
        flag_modified(u, "profile_meta")
        unlinked = True

    if unlinked:
        await db.flush()

    return json_removed or unlinked


def _place_member_entry(
    track_def: dict[str, Any],
    *,
    role: RosterRoleCode,
    entry: dict[str, Any],
    authorized_courses: list[str] | None = None,
) -> dict[str, Any]:
    """قرار دادن ردیف در محل مناسب بر اساس نوع نقش؛ دروس مجاز را همگام می‌کند."""
    label = (entry.get("name_fa") or "").strip()
    courses = (
        [str(c).strip() for c in authorized_courses if str(c or "").strip()]
        if authorized_courses is not None
        else list(
            entry.get("instructor_authorized_courses")
            or entry.get("ta_authorized_courses")
            or entry.get("authorized_courses")
            or []
        )
    )

    if role == "educational_instructor":
        # مدرس آموزشی قبلی → مدرس عادی
        prev = track_def.get("educational_instructor")
        if isinstance(prev, dict) and (prev.get("name_fa") or "").strip() and (
            (prev.get("name_fa") or "").strip() != label
        ):
            demoted = dict(prev)
            demoted["tier"] = 2
            demoted["member_kind"] = "instructor"
            demoted["roster_key"] = _slug_code("inst", (demoted.get("name_fa") or "edu"))
            instructors = list(track_def.get("instructors") or [])
            instructors.append(demoted)
            track_def["instructors"] = instructors

        new_entry = {
            "roster_key": "educational_instructor",
            "name_fa": label,
            "tier": 0,
            "member_kind": "instructor",
        }
        _write_grants_on_entry(new_entry, "instructor", courses)
        track_def["educational_instructor"] = new_entry
        return new_entry

    member_kind: MemberKind = "teaching_assistant" if role == "teaching_assistant" else "instructor"
    key_field = "teaching_assistants" if member_kind == "teaching_assistant" else "instructors"
    members = list(track_def.get(key_field) or [])
    # اگر هم‌نام از قبل هست، جایگزین کن
    members = [
        m
        for m in members
        if not (isinstance(m, dict) and (m.get("name_fa") or "").strip() == label)
    ]
    roster_key = entry.get("roster_key") or _slug_code(
        "ta" if member_kind == "teaching_assistant" else "inst", label
    )
    if roster_key == "educational_instructor":
        roster_key = _slug_code("inst", label)
    new_entry = {
        "roster_key": roster_key,
        "name_fa": label,
        "tier": 3 if member_kind == "teaching_assistant" else 2,
        "member_kind": member_kind,
    }
    _write_grants_on_entry(new_entry, member_kind, courses)
    members.append(new_entry)
    track_def[key_field] = members
    return new_entry


async def change_member_kind(
    db: AsyncSession,
    *,
    track: str,
    name_fa: str,
    kind: MemberKind,
    new_role: RosterRoleCode,
    user_id: Optional[Any] = None,
    authorized_courses: list[str] | None = None,
) -> dict[str, Any]:
    """تغییر نوع عضو در چارت: مدرس / کمک‌مدرس / مدرس آموزشی."""
    import uuid as _uuid

    from sqlalchemy.orm.attributes import flag_modified

    track_code = (track or "").strip()
    label = (name_fa or "").strip()
    if not track_code:
        raise ValueError("رسته انتخاب نشده است")
    if not label:
        raise ValueError("نام عضو خالی است")
    if new_role not in ("instructor", "teaching_assistant", "educational_instructor"):
        raise ValueError("نوع عضو نامعتبر است")

    data = _load_roster_file()
    track_def = None
    for t in data.get("tracks") or []:
        if isinstance(t, dict) and t.get("code") == track_code:
            track_def = t
            break
    if track_def is None:
        raise ValueError("رسته یافت نشد")

    extracted = _extract_member_entry_from_track(track_def, name_fa=label, kind=kind)
    if extracted is None:
        extracted = {"name_fa": label, "roster_key": _slug_code("inst", label)}

    courses = authorized_courses
    if courses is None:
        courses = list(
            extracted.get(_authorized_courses_key(kind))
            or extracted.get("authorized_courses")
            or []
        )

    placed = _place_member_entry(
        track_def,
        role=new_role,
        entry=extracted,
        authorized_courses=courses,
    )
    _save_roster_file(data)

    target_kind: MemberKind = (
        "teaching_assistant" if new_role == "teaching_assistant" else "instructor"
    )

    user: User | None = None
    if user_id is not None:
        uid = user_id if isinstance(user_id, _uuid.UUID) else _uuid.UUID(str(user_id))
        user = await db.get(User, uid)
        if user is None:
            raise ValueError("کاربر یافت نشد")
    else:
        role_candidates = {kind, target_kind, "instructor", "teaching_assistant"}
        stmt = select(User).where(User.is_active.is_(True), User.role.in_(list(role_candidates)))
        result = await db.execute(stmt)
        for u in result.scalars().all():
            if (u.full_name_fa or "").strip() != label:
                continue
            if _user_matches_track(u, track_code):
                user = u
                break

    if user is not None:
        user.role = target_kind
        meta = _apply_member_grants_to_meta(
            dict(user.profile_meta or {}),
            kind=target_kind,
            roster_legacy=False,
            authorized_courses=courses,
        )
        other_key = _authorized_courses_key(
            "teaching_assistant" if target_kind == "instructor" else "instructor"
        )
        meta.pop(other_key, None)
        tracks = list(meta.get("course_committee_tracks") or [])
        if track_code not in tracks:
            tracks.append(track_code)
        meta["course_committee_tracks"] = tracks
        meta["member_kind"] = target_kind
        meta["roster_key"] = placed.get("roster_key") or meta.get("roster_key")
        if new_role == "educational_instructor":
            meta["tier"] = 0
            meta["roster_key"] = "educational_instructor"
        elif isinstance(meta.get("tier"), int) and meta.get("tier") == 0:
            meta["tier"] = 2
        user.profile_meta = meta
        flag_modified(user, "profile_meta")
        await _sync_student_ta_flags(db, user, kind=target_kind)
        await db.flush()

    return {
        "name_fa": label,
        "kind": target_kind,
        "role_code": new_role,
        "role_label_fa": {
            "instructor": "مدرس",
            "teaching_assistant": "کمک‌مدرس",
            "educational_instructor": "مدرس آموزشی",
        }[new_role],
        "user_id": str(user.id) if user else None,
        "authorized_courses": courses or [],
        "roster_key": placed.get("roster_key"),
    }


def add_member_to_roster(
    *,
    track: str,
    kind: MemberKind | RosterRoleCode,
    name_fa: str,
    roster_legacy: bool | None = None,
    authorized_courses: list[str] | None = None,
) -> dict[str, Any]:
    label = (name_fa or "").strip()
    track_code = resolve_track_code(track) or (track or "").strip()
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

    storage_kind, role_code = _split_roster_kind(kind)
    if role_code == "educational_instructor":
        existing = _extract_member_entry_from_track(track_def, name_fa=label) or {
            "name_fa": label,
            "roster_key": "educational_instructor",
            "tier": 0,
            "member_kind": "instructor",
        }
        existing["name_fa"] = label
        if roster_legacy is not None:
            existing["roster_legacy"] = roster_legacy
        placed = _place_member_entry(
            track_def,
            role="educational_instructor",
            entry=existing,
            authorized_courses=authorized_courses,
        )
        _save_roster_file(data)
        return {
            "value": placed.get("roster_key") or "educational_instructor",
            "label_fa": label,
            "source": "roster",
        }

    kind = storage_kind
    key_field = "instructors" if kind == "instructor" else "teaching_assistants"
    members = list(track_def.get(key_field) or [])
    for row in members:
        if isinstance(row, dict) and (row.get("name_fa") or "").strip() == label:
            if roster_legacy is not None:
                row["roster_legacy"] = roster_legacy
            if authorized_courses is not None:
                _write_grants_on_entry(row, kind, authorized_courses)
            track_def[key_field] = members
            _save_roster_file(data)
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
    if roster_legacy is not None:
        entry["roster_legacy"] = roster_legacy
    if authorized_courses is not None:
        _write_grants_on_entry(entry, kind, authorized_courses)
    members.append(entry)
    track_def[key_field] = members
    _save_roster_file(data)
    return {"value": roster_key, "label_fa": label, "source": "roster"}


async def sync_roster_profile_meta(
    db: AsyncSession,
    user: User,
    *,
    track: str,
    kind: MemberKind,
) -> None:
    """به‌روزرسانی رسته و نوع عضویت در پروفایل بدون تغییر نقش سامانه."""
    from sqlalchemy.orm.attributes import flag_modified

    track_code = (track or "").strip()
    if not track_code:
        return
    meta = dict(user.profile_meta or {})
    tracks = list(meta.get("course_committee_tracks") or [])
    if track_code not in tracks:
        tracks.append(track_code)
    meta["course_committee_tracks"] = tracks
    meta["member_kind"] = kind
    user.profile_meta = meta
    flag_modified(user, "profile_meta")
    await db.flush()


def _apply_member_grants_to_meta(
    meta: dict[str, Any],
    *,
    kind: MemberKind,
    roster_legacy: bool | None = None,
    authorized_courses: list[str] | None = None,
) -> dict[str, Any]:
    out = dict(meta or {})
    if roster_legacy is not None:
        out["roster_legacy"] = bool(roster_legacy)
    if authorized_courses is not None:
        key = _authorized_courses_key(kind)
        cleaned = [str(c).strip() for c in authorized_courses if str(c or "").strip()]
        out[key] = cleaned
    return out


def _sync_roster_entry_grants(
    *,
    track: str,
    kind: MemberKind,
    name_fa: str,
    roster_legacy: bool | None = None,
    authorized_courses: list[str] | None = None,
) -> bool:
    """همگام‌سازی پرچم legacy و مجوز دروس در ردیف JSON چارت. True اگر ردیفی به‌روز شد."""
    label = (name_fa or "").strip()
    track_code = (track or "").strip()
    if not label or not track_code:
        return False
    data = _load_roster_file()
    track_def = None
    for t in data.get("tracks") or []:
        if isinstance(t, dict) and t.get("code") == track_code:
            track_def = t
            break
    if track_def is None:
        return False

    grants_key = _authorized_courses_key(kind)
    cleaned = (
        [str(c).strip() for c in authorized_courses if str(c or "").strip()]
        if authorized_courses is not None
        else None
    )

    def _apply(row: dict[str, Any]) -> bool:
        changed = False
        if roster_legacy is not None:
            row["roster_legacy"] = bool(roster_legacy)
            changed = True
        if cleaned is not None:
            row[grants_key] = list(cleaned)
            row["authorized_courses"] = list(cleaned)
            # پس از تعیین دروس مشخص، پرچم «همه دروس» برداشته می‌شود
            row["roster_legacy"] = False
            changed = True
        return changed

    updated = False
    if kind == "instructor":
        edu = track_def.get("educational_instructor")
        if isinstance(edu, dict) and (edu.get("name_fa") or "").strip() == label:
            updated = _apply(edu) or updated
            track_def["educational_instructor"] = edu

    key_field = "instructors" if kind == "instructor" else "teaching_assistants"
    members = list(track_def.get(key_field) or [])
    for row in members:
        if not isinstance(row, dict) or (row.get("name_fa") or "").strip() != label:
            continue
        if _apply(row):
            updated = True
    if updated:
        track_def[key_field] = members
        _save_roster_file(data)
    return updated


async def update_member_courses(
    db: AsyncSession,
    *,
    track: str,
    kind: MemberKind,
    name_fa: str,
    authorized_courses: list[str],
    user_id: Optional[Any] = None,
) -> dict[str, Any]:
    """ویرایش دروس مجاز عضو — هم برای کاربر متصل و هم عضو فقط‌چارت."""
    import uuid as _uuid

    from sqlalchemy.orm.attributes import flag_modified

    track_code = (track or "").strip()
    label = (name_fa or "").strip()
    if not track_code:
        raise ValueError("رسته انتخاب نشده است")
    if not label:
        raise ValueError("نام عضو خالی است")
    if get_track_by_code(track_code) is None:
        raise ValueError("رسته یافت نشد")

    courses = [str(c).strip() for c in (authorized_courses or []) if str(c or "").strip()]
    user: User | None = None
    if user_id is not None:
        uid = user_id if isinstance(user_id, _uuid.UUID) else _uuid.UUID(str(user_id))
        user = await db.get(User, uid)
        if user is None:
            raise ValueError("کاربر یافت نشد")
    else:
        role_for_kind = "instructor" if kind == "instructor" else "teaching_assistant"
        stmt = select(User).where(User.is_active.is_(True), User.role == role_for_kind)
        result = await db.execute(stmt)
        for u in result.scalars().all():
            if (u.full_name_fa or "").strip() == label and _user_matches_track(u, track_code):
                user = u
                break

    synced = _sync_roster_entry_grants(
        track=track_code,
        kind=kind,
        name_fa=label,
        roster_legacy=False,
        authorized_courses=courses,
    )

    if user is not None:
        meta = _apply_member_grants_to_meta(
            dict(user.profile_meta or {}),
            kind=kind,
            roster_legacy=False,
            authorized_courses=courses,
        )
        tracks = list(meta.get("course_committee_tracks") or [])
        if track_code not in tracks:
            tracks.append(track_code)
        meta["course_committee_tracks"] = tracks
        meta["member_kind"] = kind
        user.profile_meta = meta
        flag_modified(user, "profile_meta")
        await db.flush()
        return {
            "name_fa": label,
            "user_id": str(user.id),
            "authorized_courses": courses,
            "source": "user",
        }

    if not synced:
        # عضو فقط در لیست کاربران بدون ردیف JSON — ایجاد ردیف سبک در چارت
        add_member_to_roster(
            track=track_code,
            kind=kind,
            name_fa=label,
            roster_legacy=False,
            authorized_courses=courses,
        )
        return {
            "name_fa": label,
            "user_id": None,
            "authorized_courses": courses,
            "source": "roster",
        }

    return {
        "name_fa": label,
        "user_id": None,
        "authorized_courses": courses,
        "source": "roster",
    }


async def update_member_grants(
    db: AsyncSession,
    user: User,
    *,
    track: str,
    kind: MemberKind,
    roster_legacy: bool | None = None,
    authorized_courses: list[str] | None = None,
) -> User:
    """به‌روزرسانی مجوز درس و پرچم پرسنل موجود برای عضو چارت."""
    from sqlalchemy.orm.attributes import flag_modified

    track_code = (track or "").strip()
    if not track_code:
        raise ValueError("رسته انتخاب نشده است")

    meta = _apply_member_grants_to_meta(
        dict(user.profile_meta or {}),
        kind=kind,
        roster_legacy=roster_legacy,
        authorized_courses=authorized_courses,
    )
    tracks = list(meta.get("course_committee_tracks") or [])
    if track_code not in tracks:
        tracks.append(track_code)
    meta["course_committee_tracks"] = tracks
    meta["member_kind"] = kind
    user.profile_meta = meta
    flag_modified(user, "profile_meta")

    name_fa = (user.full_name_fa or "").strip()
    if name_fa:
        _sync_roster_entry_grants(
            track=track_code,
            kind=kind,
            name_fa=name_fa,
            roster_legacy=roster_legacy,
            authorized_courses=authorized_courses,
        )

    await db.flush()
    return user


async def _sync_student_ta_flags(
    db: AsyncSession,
    user: User,
    *,
    kind: MemberKind,
) -> None:
    """برای کاربران دانشجو — پرچم‌های کمک‌مدرسی/مدرس در extra_data."""
    from sqlalchemy.orm.attributes import flag_modified

    from app.models.operational_models import Student

    result = await db.execute(select(Student).where(Student.user_id == user.id))
    student = result.scalars().first()
    if student is None:
        return
    extra = dict(student.extra_data or {})
    if kind == "teaching_assistant":
        extra["is_teaching_assistant"] = True
        extra["ta_registered"] = True
    elif kind == "instructor":
        extra["rank"] = "instructor"
    student.extra_data = extra
    flag_modified(student, "extra_data")
    await db.flush()


async def link_user_to_roster(
    db: AsyncSession,
    user: User,
    *,
    track: str,
    kind: MemberKind | RosterRoleCode,
    roster_legacy: bool | None = None,
    authorized_courses: list[str] | None = None,
) -> User:
    """اتصال کاربر موجود به چارت کمیته دروس."""
    from sqlalchemy.orm.attributes import flag_modified

    track_code = (track or "").strip()
    if not track_code:
        raise ValueError("رسته انتخاب نشده است")
    if not get_track_by_code(track_code):
        raise ValueError("رسته یافت نشد")

    label = (user.full_name_fa or user.username or "").strip()
    if not label:
        raise ValueError("نام فارسی کاربر خالی است")

    storage_kind, role_code = _split_roster_kind(kind)
    user.role = storage_kind
    user.is_active = True

    entry = add_member_to_roster(
        track=track_code,
        kind=kind,
        name_fa=label,
        roster_legacy=roster_legacy,
        authorized_courses=authorized_courses,
    )

    meta = _apply_member_grants_to_meta(
        dict(user.profile_meta or {}),
        kind=storage_kind,
        roster_legacy=roster_legacy,
        authorized_courses=authorized_courses,
    )
    tracks = list(meta.get("course_committee_tracks") or [])
    if track_code not in tracks:
        tracks.append(track_code)
    meta["course_committee_tracks"] = tracks
    meta["member_kind"] = storage_kind
    meta["roster_key"] = entry.get("value") or meta.get("roster_key")
    if role_code == "educational_instructor":
        meta["tier"] = 0
        meta["roster_key"] = "educational_instructor"
    elif isinstance(meta.get("tier"), int) and meta.get("tier") == 0:
        meta["tier"] = 2
    user.profile_meta = meta
    flag_modified(user, "profile_meta")

    await _sync_student_ta_flags(db, user, kind=storage_kind)
    await db.flush()
    return user


async def register_teaching_assistant_on_roster(
    db: AsyncSession,
    *,
    track: str,
    name_fa: str,
    user: User | None = None,
) -> None:
    """افزودن کمک‌مدرس به چارت و همگام‌سازی کاربر سامانه."""
    label = (name_fa or "").strip()
    track_code = (track or "").strip()
    if not label or not track_code:
        return
    if not get_track_by_code(track_code):
        add_track_to_roster(track_label_fa_from_code(track_code), code=track_code)
    entry = add_member_to_roster(track=track_code, kind="teaching_assistant", name_fa=label)
    if user:
        if label and not (user.full_name_fa or "").strip():
            user.full_name_fa = label
        await sync_roster_profile_meta(db, user, track=track_code, kind="teaching_assistant")
    else:
        await ensure_roster_user(
            db,
            track=track_code,
            kind="teaching_assistant",
            name_fa=label,
            roster_key=str(entry.get("value") or ""),
        )


async def promote_ta_to_instructor_on_roster(
    db: AsyncSession,
    *,
    track: str,
    name_fa: str,
    user: User | None = None,
) -> None:
    """حذف از لیست کمک‌مدرسین و افزودن به لیست مدرسین یک رسته."""
    label = (name_fa or "").strip()
    track_code = (track or "").strip()
    if not label or not track_code:
        return
    if not get_track_by_code(track_code):
        add_track_to_roster(track_label_fa_from_code(track_code), code=track_code)
    remove_member_from_roster(track=track_code, kind="teaching_assistant", name_fa=label)
    entry = add_member_to_roster(track=track_code, kind="instructor", name_fa=label)
    if user:
        await sync_roster_profile_meta(db, user, track=track_code, kind="instructor")
    else:
        await ensure_roster_user(
            db,
            track=track_code,
            kind="instructor",
            name_fa=label,
            roster_key=str(entry.get("value") or ""),
        )


def track_label_fa_from_code(track_code: str) -> str:
    """برچسب فارسی رسته — از چارت یا خود کد."""
    track_def = get_track_by_code(track_code)
    if track_def:
        return str(track_def.get("name_fa") or track_code)
    try:
        from app.services.ta_track_change_service import track_label_fa

        return track_label_fa(track_code)
    except Exception:
        return str(track_code or "—")


def resolve_track_code(track_ref: str) -> str | None:
    """کد رسته از کد یا برچسب فارسی."""
    raw = (track_ref or "").strip()
    if not raw:
        return None
    if get_track_by_code(raw) is not None:
        return raw
    raw_n = _normalize_fa(raw)
    for opt in list_track_options():
        val = str(opt.get("value") or "").strip()
        lab = str(opt.get("label_fa") or "").strip()
        if raw == lab or raw_n == _normalize_fa(lab) or raw == val:
            return val or None
    return None


def resolve_track_display_fa(track_ref: str) -> str:
    """برچسب فارسی قابل‌نمایش رسته برای جداول اپراتور."""
    raw = (track_ref or "").strip()
    if not raw:
        return ""
    code = resolve_track_code(raw) or raw
    label = track_label_fa_from_code(code)
    return label if label else raw


async def ensure_roster_user(
    db: AsyncSession,
    *,
    track: str,
    kind: MemberKind | RosterRoleCode,
    name_fa: str,
    roster_key: str | None = None,
    roster_legacy: bool | None = None,
    authorized_courses: list[str] | None = None,
) -> User:
    """ایجاد کاربر سامانه برای عضو جدید چارت (در صورت نبود)."""
    from app.api.auth import get_password_hash

    label = (name_fa or "").strip()
    track_code = (track or "").strip()
    storage_kind, role_code = _split_roster_kind(kind)
    role = storage_kind
    rk = (roster_key or _slug_code("inst" if storage_kind == "instructor" else "ta", label)).strip()
    if role_code == "educational_instructor":
        rk = "educational_instructor"
    username = f"cc_{track_code}_{rk}"[:80]

    result = await db.execute(select(User).where(User.username == username))
    user = result.scalars().first()
    profile_meta = _apply_member_grants_to_meta(
        {
            "course_committee_tracks": [track_code],
            "member_kind": storage_kind,
            "roster_key": rk,
            **({"tier": 0} if role_code == "educational_instructor" else {}),
        },
        kind=storage_kind,
        roster_legacy=roster_legacy,
        authorized_courses=authorized_courses,
    )
    if user:
        user.full_name_fa = label
        user.role = role
        user.is_active = True
        meta = _apply_member_grants_to_meta(
            dict(user.profile_meta or {}),
            kind=storage_kind,
            roster_legacy=roster_legacy,
            authorized_courses=authorized_courses,
        )
        tracks = list(meta.get("course_committee_tracks") or [])
        if track_code not in tracks:
            tracks.append(track_code)
        meta["course_committee_tracks"] = tracks
        meta["member_kind"] = storage_kind
        meta["roster_key"] = rk
        if role_code == "educational_instructor":
            meta["tier"] = 0
        user.profile_meta = meta
        return user

    user = User(
        id=__import__("uuid").uuid4(),
        username=username,
        email=f"{username}@course-committee.anistito.local",
        hashed_password=get_password_hash("demo123"),
        portal_password_plain=None,
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
        track = (
            str(row.get("track_code") or "").strip()
            or resolve_track_code(str(row.get("track") or "").strip())
            or (row.get("track") or "").strip()
        )
        track_label = track_label_fa_from_code(track) if track else ""
        if not track_label:
            track_label = track
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


def _normalize_fa(text: str) -> str:
    """یکسان‌سازی ی/ک عربی و فارسی برای تطبیق نام‌ها."""
    s = (text or "").strip()
    return (
        s.replace("ي", "ی")
        .replace("ك", "ک")
        .replace("ة", "ه")
        .replace("‌", "")
    )


def _find_roster_option(members: list[dict[str, Any]], raw: str) -> dict[str, Any] | None:
    needle = (raw or "").strip()
    if not needle:
        return None
    needle_fa = _normalize_fa(needle)
    for member in members:
        val = str(member.get("value") or "").strip()
        lab = _normalize_fa(str(member.get("label_fa") or "").strip())
        name = _normalize_fa(str(member.get("name_fa") or "").strip())
        if needle == val or needle_fa == lab or (name and needle_fa == name):
            return member
    return None


def _course_label_and_code(course_ref: str) -> tuple[str, str]:
    """برچسب فارسی و کد درس از ارجاع (کد یا نام)."""
    raw = (course_ref or "").strip()
    if not raw:
        return "", ""
    raw_n = _normalize_fa(raw)
    for row in list_course_catalog_options():
        val = (row.get("value") or "").strip()
        lab = (row.get("label_fa") or "").strip()
        if raw == val or raw == lab or raw_n == _normalize_fa(val) or raw_n == _normalize_fa(lab):
            return lab or val, val
    return raw, raw


def _row_identity_key(course_name: str, instructor: str, instructor_id: str | None = None) -> str:
    course = _normalize_fa(course_name or "")
    iid = (instructor_id or "").strip()
    if iid:
        return f"{course}|id:{iid}"
    return f"{course}|name:{_normalize_fa(instructor or '')}"


async def build_course_table_rows_from_roster(db: AsyncSession) -> list[dict[str, Any]]:
    """ساخت ردیف‌های جدول لیست دروس از وصل درس↔مدرس در پیش‌آماده‌سازی.

    یک ردیف به‌ازای هر جفت درس↔مدرس مجاز. کمک‌مدرس فقط اگر دقیقاً یک نفر
    برای آن درس مجاز باشد پر می‌شود؛ در غیر این صورت خالی می‌ماند تا از فهرست انتخاب شود.
    درس بدون مدرس وصل‌شده در جدول نمی‌آید.
    """
    catalog = list_course_catalog_options()
    catalog_by_ref: dict[str, dict[str, str]] = {}
    for c in catalog:
        val = (c.get("value") or "").strip()
        lab = (c.get("label_fa") or "").strip()
        if val:
            catalog_by_ref[val] = c
        if lab:
            catalog_by_ref[lab] = c

    tracks = list_track_options()
    # course_code → list of (instructor_detail, track_code)
    pairs: list[dict[str, Any]] = []
    # course_code → list of TA details
    tas_by_course: dict[str, list[dict[str, Any]]] = {}

    for track_opt in tracks:
        track_code = str(track_opt.get("value") or "").strip()
        if not track_code:
            continue
        detail = await list_track_roster_detail(db, track=track_code)
        for inst in detail.get("instructors") or []:
            if not isinstance(inst, dict):
                continue
            grants = inst.get("authorized_courses") or []
            if not isinstance(grants, list) or not grants:
                continue
            for grant in grants:
                course_ref = str(grant or "").strip()
                if not course_ref:
                    continue
                course_opt = catalog_by_ref.get(course_ref)
                if not course_opt:
                    # هنوز در کاتالوگ نیست — رد
                    continue
                course_code = (course_opt.get("value") or course_ref).strip()
                course_label = (course_opt.get("label_fa") or course_code).strip()
                track_for_course = (course_opt.get("track") or track_code).strip()
                track_label = resolve_track_display_fa(track_for_course) or track_for_course
                pairs.append(
                    {
                        "course_name": course_label,
                        "course_code": course_code,
                        "track": track_label,
                        "track_code": track_for_course,
                        "instructor": _normalize_fa(
                            (inst.get("label_fa") or inst.get("name_fa") or "").strip()
                        ),
                        "instructor_id": (inst.get("user_id") or inst.get("value") or "").strip() or None,
                    }
                )
        for ta in detail.get("teaching_assistants") or []:
            if not isinstance(ta, dict):
                continue
            grants = ta.get("authorized_courses") or []
            if not isinstance(grants, list):
                continue
            for grant in grants:
                course_ref = str(grant or "").strip()
                if not course_ref:
                    continue
                course_opt = catalog_by_ref.get(course_ref)
                if not course_opt:
                    continue
                course_code = (course_opt.get("value") or course_ref).strip()
                tas_by_course.setdefault(course_code, []).append(ta)

    # حذف تکراری بر اساس course+instructor
    seen: set[str] = set()
    rows: list[dict[str, Any]] = []
    for pair in pairs:
        key = _row_identity_key(
            pair["course_name"],
            pair["instructor"],
            pair.get("instructor_id"),
        )
        if key in seen:
            continue
        seen.add(key)
        course_code = pair["course_code"]
        ta_list = tas_by_course.get(course_code) or []
        ta_name = ""
        ta_id = None
        if len(ta_list) == 1:
            ta = ta_list[0]
            ta_name = _normalize_fa((ta.get("label_fa") or ta.get("name_fa") or "").strip())
            ta_id = (ta.get("user_id") or ta.get("value") or "").strip() or None
        row: dict[str, Any] = {
            "course_name": pair["course_name"],
            "track": pair["track"],
            "proposed_day": "",
            "proposed_time": "",
            "instructor": pair["instructor"],
            "teaching_assistant": ta_name,
        }
        if pair.get("track_code"):
            row["track_code"] = pair["track_code"]
        if pair.get("course_code"):
            row["course_code"] = pair["course_code"]
            units = catalog_units_for_course(pair["course_code"])
            if units:
                row["units"] = units
        if pair.get("instructor_id"):
            row["instructor_id"] = pair["instructor_id"]
        if ta_id:
            row["teaching_assistant_id"] = ta_id
        rows.append(row)

    rows.sort(key=lambda r: (r.get("track") or "", r.get("course_name") or "", r.get("instructor") or ""))
    return rows


def merge_course_table_rows_with_roster(
    existing: Any,
    roster_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """همگام‌سازی جدول موجود با چارت: روز/ساعت حفظ؛ ردیف خارج از چارت حذف؛ ردیف جدید اضافه."""
    existing_list = existing if isinstance(existing, list) else []

    def _index_keys(row: dict[str, Any]) -> list[str]:
        course = str(row.get("course_name") or "").strip()
        if not course:
            return []
        instructor = str(row.get("instructor") or "").strip()
        instructor_id = str(row.get("instructor_id") or "").strip() or None
        label, code = _course_label_and_code(course)
        keys: list[str] = []
        for cname in {course, label, code}:
            if not cname:
                continue
            keys.append(_row_identity_key(cname, instructor, instructor_id))
            # تطبیق فقط با نام (وقتی یکی id دارد و دیگری نه)
            if instructor:
                keys.append(_row_identity_key(cname, instructor, None))
        return keys

    by_key: dict[str, dict[str, Any]] = {}
    for row in existing_list:
        if not isinstance(row, dict):
            continue
        for k in _index_keys(row):
            by_key[k] = row

    merged: list[dict[str, Any]] = []
    for base in roster_rows:
        prev = None
        for k in _index_keys(base):
            prev = by_key.get(k)
            if prev:
                break
        row = dict(base)
        if prev:
            for sched_key in ("proposed_day", "proposed_time", "day", "time"):
                val = prev.get(sched_key)
                if val not in (None, ""):
                    if sched_key in ("day", "proposed_day"):
                        row["proposed_day"] = val
                    elif sched_key in ("time", "proposed_time"):
                        row["proposed_time"] = val
            if not row.get("teaching_assistant") and prev.get("teaching_assistant"):
                row["teaching_assistant"] = prev.get("teaching_assistant")
                if prev.get("teaching_assistant_id"):
                    row["teaching_assistant_id"] = prev.get("teaching_assistant_id")
            for loc_key in ("classroom_location", "instructor_coordinated"):
                if prev.get(loc_key) not in (None, ""):
                    row[loc_key] = prev[loc_key]
        merged.append(row)
    return merged


async def validate_semester_prep_course_table_rows(
    db: AsyncSession,
    rows: Any,
) -> list[str]:
    """اعتبارسنجی ردیف‌های جدول دروس نسبت به کاتالوگ و چارت پیش‌آماده‌سازی.

    برمی‌گرداند فهرست پیام‌های خطا (خالی = معتبر).
    """
    if not isinstance(rows, list):
        return ["جدول دروس نامعتبر است"]
    errors: list[str] = []
    catalog = list_course_catalog_options()
    catalog_refs: set[str] = set()
    for c in catalog:
        if c.get("value"):
            catalog_refs.add(str(c["value"]).strip())
        if c.get("label_fa"):
            catalog_refs.add(str(c["label_fa"]).strip())

    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"ردیف {i + 1}: نامعتبر")
            continue
        course = str(row.get("course_name") or "").strip()
        if not course:
            continue
        if course not in catalog_refs:
            errors.append(f"درس «{course}» در کاتالوگ پیش‌آماده‌سازی نیست")
            continue
        track = (
            str(row.get("track_code") or "").strip()
            or resolve_track_code(str(row.get("track") or ""))
            or resolve_track_for_course(course)
            or ""
        )
        instructor = str(row.get("instructor") or row.get("instructor_id") or "").strip()
        if instructor and track:
            members = await list_members(db, track=track, kind="instructor")
            hit = _find_roster_option(members, instructor)
            if hit is None:
                errors.append(f"مدرس «{instructor}» در رستهٔ این درس در چارت نیست")
            elif not option_authorized_for_course(hit, "instructor", course):
                errors.append(f"مدرس «{instructor}» برای این درس در چارت مجاز نیست")
        ta = str(row.get("teaching_assistant") or row.get("teaching_assistant_id") or "").strip()
        if ta and track:
            members = await list_members(db, track=track, kind="teaching_assistant")
            hit = _find_roster_option(members, ta)
            if hit is None:
                errors.append(f"کمک‌مدرس «{ta}» در رستهٔ این درس در چارت نیست")
            elif not option_authorized_for_course(hit, "teaching_assistant", course):
                errors.append(f"کمک‌مدرس «{ta}» برای این درس در چارت مجاز نیست")
    return errors
