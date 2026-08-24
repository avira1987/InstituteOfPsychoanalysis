"""قالب یکپارچهٔ هویت دانشجو: شماره و نام کاربری هر دو ``STU-{n}`` (از STU-1001).

کدهای قدیمی ``INT-018`` / ``INT-ADV-001`` و نام‌های کاربری موبایل یا اسلاگ
(مثل ``azin_darayan``) هنگام ساخت پرونده یا در مهاجرت استارت‌آپ به همین قالب تبدیل می‌شوند.
ورود با موبایل (OTP) و نام کاربری قدیمی همچنان کار می‌کند.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.core.user_roles import normalize_user_roles
from app.models.operational_models import Student, User

logger = logging.getLogger(__name__)

STUDENT_CODE_PREFIX = "STU"
STUDENT_CODE_BASE = 1000  # اولین شمارهٔ واقعی: STU-1001
CANONICAL_CODE_RE = re.compile(r"^STU-(\d+)$", re.I)
LEGACY_INT_RE = re.compile(r"^INT-(\d+)$", re.I)
LEGACY_INT_ADV_RE = re.compile(r"^INT-ADV-(\d+)$", re.I)
_SKIP_CODE_PREFIXES = ("AUTO-", "DEMO-", "INST-", "FLOW-", "AUTO-PROFILE-")
_PROTECTED_USERNAMES = frozenset({"admin", "system_actor"})
_STAFF_ROLES_BLOCK_RENAME = frozenset({
    "admin", "staff", "finance", "deputy_education", "site_manager",
})


def format_student_code(n: int) -> str:
    return f"{STUDENT_CODE_PREFIX}-{int(n)}"


def parse_canonical_stu_number(code: str | None) -> Optional[int]:
    m = CANONICAL_CODE_RE.match((code or "").strip())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def is_canonical_student_code(code: str | None) -> bool:
    n = parse_canonical_stu_number(code)
    return n is not None and n > STUDENT_CODE_BASE


def is_canonical_student_username(username: str | None) -> bool:
    return is_canonical_student_code((username or "").strip())


def is_legacy_intern_code(code: str | None) -> bool:
    s = (code or "").strip()
    return bool(LEGACY_INT_RE.match(s) or LEGACY_INT_ADV_RE.match(s))


def _skip_code(code: str | None) -> bool:
    s = (code or "").strip()
    if not s:
        return True
    upper = s.upper()
    return any(upper.startswith(p) for p in _SKIP_CODE_PREFIXES)


def _legacy_intern_sort_key(code: str) -> tuple[int, int]:
    s = (code or "").strip()
    m = LEGACY_INT_ADV_RE.match(s)
    if m:
        return (1, int(m.group(1)))
    m = LEGACY_INT_RE.match(s)
    if m:
        return (0, int(m.group(1)))
    return (9, 0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def next_student_code(db: AsyncSession) -> str:
    """STU-<n+1> از روی بزرگ‌ترین عدد STU- موجود (نه COUNT) تا با حذف/seed تصادم ندهد."""
    rows = await db.execute(select(Student.student_code).where(Student.student_code.like("STU-%")))
    max_num = STUDENT_CODE_BASE
    for code in rows.scalars().all():
        n = parse_canonical_stu_number(code)
        if n is not None and n > max_num:
            max_num = n
    return format_student_code(max_num + 1)


def _can_rewrite_username(user: User) -> bool:
    uname = (user.username or "").strip()
    if uname.lower() in _PROTECTED_USERNAMES:
        return False
    roles = {str(r).strip().lower() for r in normalize_user_roles(user)}
    if roles & _STAFF_ROLES_BLOCK_RENAME:
        return False
    return True


def _remember_legacy_username(user: User, old_username: str) -> None:
    old = (old_username or "").strip()
    if not old:
        return
    meta = dict(user.profile_meta) if isinstance(user.profile_meta, dict) else {}
    names = [str(x).strip() for x in (meta.get("legacy_usernames") or []) if str(x).strip()]
    if old not in names:
        names.append(old)
    meta["legacy_usernames"] = names[-20:]
    meta["legacy_username"] = old
    user.profile_meta = meta
    flag_modified(user, "profile_meta")


def _remember_legacy_student_code(student: Student, old_code: str, old_username: str | None = None) -> None:
    extra = dict(student.extra_data) if isinstance(student.extra_data, dict) else {}
    if old_code and not extra.get("legacy_student_code"):
        extra["legacy_student_code"] = old_code
    if old_username and not extra.get("legacy_username"):
        extra["legacy_username"] = old_username
    extra["identity_unified_at"] = _now_iso()
    student.extra_data = extra
    flag_modified(student, "extra_data")


async def _username_taken(db: AsyncSession, username: str, *, except_user_id) -> bool:
    row = await db.execute(
        select(User.id).where(User.username == username, User.id != except_user_id).limit(1)
    )
    return row.scalar_one_or_none() is not None


async def sync_student_username(db: AsyncSession, user: User, student_code: str) -> bool:
    """نام کاربری دانشجو را با شمارهٔ دانشجویی یکی می‌کند. True اگر عوض شد."""
    target = (student_code or "").strip()
    if not target or not is_canonical_student_code(target):
        return False
    if not user or not _can_rewrite_username(user):
        return False
    current = (user.username or "").strip()
    if current == target:
        return False
    if await _username_taken(db, target, except_user_id=user.id):
        logger.warning("student username %s already taken; skip rename from %s", target, current)
        return False
    if current and current != target:
        _remember_legacy_username(user, current)
    user.username = target
    return True


async def unify_student_identity(db: AsyncSession, student: Student, user: User | None = None) -> dict:
    """کد INT-* را به STU-* تبدیل و نام کاربری را هم‌تراز می‌کند."""
    changed_code = False
    changed_username = False
    if student is None or getattr(student, "is_sample_data", False):
        return {"code": False, "username": False}
    code = (student.student_code or "").strip()
    if _skip_code(code):
        return {"code": False, "username": False}

    if user is None and student.user_id:
        user = await db.get(User, student.user_id)

    old_username = (user.username or "").strip() if user else ""

    if is_legacy_intern_code(code):
        new_code = await next_student_code(db)
        _remember_legacy_student_code(student, code, old_username or None)
        student.student_code = new_code
        changed_code = True
        code = new_code
        await db.flush()

    if user and is_canonical_student_code(code):
        if old_username and old_username != code:
            extra = dict(student.extra_data) if isinstance(student.extra_data, dict) else {}
            if not extra.get("legacy_username"):
                extra["legacy_username"] = old_username
                student.extra_data = extra
                flag_modified(student, "extra_data")
        changed_username = await sync_student_username(db, user, code)
        if changed_username:
            await db.flush()

    return {"code": changed_code, "username": changed_username}


async def unify_existing_student_identities(db: AsyncSession) -> dict:
    """مهاجرت دانشجویان موجود: INT-* → STU-* و نام کاربری = شماره دانشجویی."""
    stmt = (
        select(Student)
        .where(Student.is_sample_data.is_(False))
        .order_by(Student.created_at.asc())
    )
    students = list((await db.execute(stmt)).scalars().all())
    intern_rows = [s for s in students if is_legacy_intern_code(s.student_code)]
    intern_rows.sort(key=lambda s: _legacy_intern_sort_key(s.student_code or ""))
    rest = [s for s in students if s not in intern_rows]

    codes = 0
    usernames = 0
    for student in intern_rows + rest:
        user = await db.get(User, student.user_id) if student.user_id else None
        result = await unify_student_identity(db, student, user)
        if result["code"]:
            codes += 1
        if result["username"]:
            usernames += 1
    return {"codes": codes, "usernames": usernames, "scanned": len(students)}


async def find_user_for_password_login(db: AsyncSession, raw_username: str) -> Optional[User]:
    """ورود با نام کاربری STU-…، کد قدیمی INT-…، اسلاگ قدیمی، یا شماره موبایل."""
    from app.api.auth import normalize_login_field
    from app.demo_role_users import resolve_portal_login_username

    resolved = resolve_portal_login_username(normalize_login_field(raw_username))
    if not resolved:
        return None

    user = (await db.execute(select(User).where(User.username == resolved))).scalars().first()
    if user:
        return user

    upper = resolved.upper()
    if upper != resolved:
        user = (await db.execute(select(User).where(User.username == upper))).scalars().first()
        if user:
            return user

    for code in dict.fromkeys([upper, resolved]):
        st = (
            await db.execute(select(Student).where(Student.student_code == code))
        ).scalars().first()
        if st and st.user_id:
            u = await db.get(User, st.user_id)
            if u:
                return u

    st = (
        await db.execute(
            select(Student).where(Student.extra_data["legacy_student_code"].as_string() == upper)
        )
    ).scalars().first()
    if st and st.user_id:
        u = await db.get(User, st.user_id)
        if u:
            return u

    user = (
        await db.execute(
            select(User).where(User.profile_meta["legacy_username"].as_string() == resolved)
        )
    ).scalars().first()
    if user:
        return user

    st = (
        await db.execute(
            select(Student).where(Student.extra_data["legacy_username"].as_string() == resolved)
        )
    ).scalars().first()
    if st and st.user_id:
        u = await db.get(User, st.user_id)
        if u:
            return u

    from app.services.sms_gateway import normalize_ir_mobile

    phone = normalize_ir_mobile(resolved)
    if phone:
        from app.services.otp_service import find_user_by_login_phone

        found = await find_user_by_login_phone(db, phone)
        if found:
            return found
    return None
