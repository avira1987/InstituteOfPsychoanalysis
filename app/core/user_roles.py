"""نقش‌های چندگانهٔ کاربر پورتال — primary در User.role، لیست در User.roles."""

from __future__ import annotations

from typing import Any, Iterable, Sequence

from sqlalchemy import or_
from sqlalchemy.sql import ColumnElement

from app.meta.role_labels import normalize_role_code, role_labels_map


def normalize_roles_list(raw: Any, *, primary: str | None = None) -> list[str]:
    """نرمال‌سازی آرایهٔ نقش‌ها؛ ترتیب حفظ می‌شود و تکراری حذف می‌شود."""
    out: list[str] = []
    seen: set[str] = set()
    if isinstance(raw, (list, tuple)):
        for item in raw:
            code = normalize_role_code(item if isinstance(item, str) else str(item or ""))
            if not code or code in seen:
                continue
            seen.add(code)
            out.append(code)
    primary_norm = normalize_role_code(primary)
    if primary_norm and primary_norm not in seen:
        out.insert(0, primary_norm)
        seen.add(primary_norm)
    if not out and primary_norm:
        out = [primary_norm]
    return out


def normalize_user_roles(user: Any) -> list[str]:
    """لیست نقش‌های کاربر؛ اگر roles خالی/نامعتبر باشد از role استفاده می‌شود."""
    if user is None:
        return []
    primary = getattr(user, "role", None)
    roles_attr = getattr(user, "roles", None)
    roles = normalize_roles_list(roles_attr, primary=primary)
    if roles:
        return roles
    code = normalize_role_code(primary)
    return [code] if code else []


# نقش‌های سازمانی که قابلیت نقش‌های پورتال را هم دارند
_ROLE_IMPLIES: dict[str, frozenset[str]] = {
    # هیئت علمی — سوپرویژن و مصاحبه
    "faculty_1": frozenset({"supervisor", "interviewer"}),
    # مدرس آموزشی — همان قابلیت‌های مدرس
    "educational_instructor": frozenset({"instructor"}),
    # مدیر داخلی — همان دسترسی‌های کارمند دفتر
    "internal_manager": frozenset({"staff"}),
}

# نقش ورود که برای خانه/کارتابل/ترنزیشن معادل نقش دیگری است
_PORTAL_ROLE_CANONICAL: dict[str, str] = {
    "internal_manager": "staff",
}

# فقط این impliedها هنگام ذخیره روی User.roles نوشته می‌شوند
_ROLE_PORTAL_GRANTS: dict[str, frozenset[str]] = {
    "internal_manager": frozenset({"staff"}),
    "faculty_1": frozenset({"interviewer", "supervisor"}),
    "educational_instructor": frozenset({"instructor"}),
}


def canonical_portal_role(code: str | None) -> str:
    """نقش ذخیره‌شده را به نقش پورتال معادل برای دسترسی/خانه تبدیل می‌کند."""
    normalized = normalize_role_code(code)
    if not normalized:
        return ""
    return _PORTAL_ROLE_CANONICAL.get(normalized, normalized)


def role_grants(code: str | None, *targets: str) -> bool:
    """آیا این کد نقش، خودِ هدف است یا آن را implied می‌کند (مثلاً faculty_1 → interviewer)."""
    code_n = canonical_portal_role(code) or normalize_role_code(code)
    needed = {normalize_role_code(t) for t in targets if t}
    needed.discard("")
    if not code_n or not needed:
        return False
    return bool(_expanded_roles({code_n}) & needed)


def _expanded_roles(have: set[str]) -> set[str]:
    out = set(have)
    for code in list(have):
        out |= _ROLE_IMPLIES.get(code, frozenset())
    return out


def expanded_user_roles(user: Any) -> set[str]:
    """نقش‌های ذخیره‌شده به‌علاوه implied (مثلاً faculty_1 → supervisor)."""
    return _expanded_roles(set(normalize_user_roles(user)))


def ordered_actor_roles(user: Any) -> list[str]:
    """نقش‌های قابل‌اقدام: اول primary، بعد بقیهٔ ذخیره‌شده، بعد implied؛ بدون تکرار."""
    stored = normalize_user_roles(user)
    prim = primary_role(user)
    ordered: list[str] = []
    seen: set[str] = set()

    def _add(code: str | None) -> None:
        n = normalize_role_code(code)
        if not n or n in seen:
            return
        seen.add(n)
        ordered.append(n)

    _add(prim)
    for code in stored:
        _add(code)
    for code in list(ordered):
        for implied in sorted(_ROLE_IMPLIES.get(code, frozenset())):
            _add(implied)
    return ordered


def candidate_actor_roles(actor_role: str | None, user: Any | None) -> list[str]:
    """نقش‌هایی که موتور برای RBAC امتحان می‌کند. system و نبود User: همان رشته."""
    hint = normalize_role_code(actor_role) if actor_role else ""
    if not hint and actor_role:
        hint = str(actor_role).strip()
    if hint == "system" or user is None:
        return [hint or (actor_role or "").strip() or "student"]
    ordered = ordered_actor_roles(user)
    if hint and hint not in ordered:
        ordered.append(hint)
    return ordered or [hint or "student"]


_STUDENT_PORTAL_ROLES = frozenset({"student", "applicant"})


def operator_portal_roles(user: Any) -> list[str]:
    """نقش‌های عملیاتی برای کارتابل/آمادگی؛ primary دانشجو → خالی."""
    if primary_role(user) == "student":
        return []
    return [c for c in ordered_actor_roles(user) if c not in _STUDENT_PORTAL_ROLES]


def user_has_role(user: Any, *codes: str, admin_bypass: bool = True) -> bool:
    """آیا کاربر حداقل یکی از نقش‌های داده‌شده را دارد؟"""
    needed = {normalize_role_code(c) for c in codes if c}
    needed.discard("")
    if not needed:
        return False
    have = _expanded_roles(set(normalize_user_roles(user)))
    if admin_bypass and "admin" in have:
        return True
    return bool(have & needed)


def user_has_any_role(user: Any, codes: Iterable[str], *, admin_bypass: bool = True) -> bool:
    return user_has_role(user, *list(codes), admin_bypass=admin_bypass)


def primary_role(user: Any) -> str:
    """نقش اصلی برای خانهٔ ورود / نمایش پیش‌فرض."""
    if user is None:
        return "student"
    code = normalize_role_code(getattr(user, "role", None))
    if code:
        return code
    roles = normalize_user_roles(user)
    return roles[0] if roles else "student"


def sync_primary_and_roles(
    roles: Sequence[str] | None,
    primary: str | None = None,
) -> tuple[str, list[str]]:
    """
    همگام‌سازی primary و لیست نقش‌ها.
    primary باید عضو roles باشد؛ در غیر این صورت اولین نقش لیست.
    """
    cleaned = normalize_roles_list(list(roles or []), primary=primary)
    if not cleaned:
        raise ValueError("حداقل یک نقش الزامی است")
    known = set(role_labels_map().keys())
    unknown = [r for r in cleaned if r not in known]
    if unknown:
        raise ValueError(f"نقش نامعتبر: {', '.join(unknown)}")
    # مدیر داخلی: staff را هم روی حساب بنویس تا منو و بررسی‌های آرایهٔ نقش برقرار بماند
    granted: list[str] = []
    seen = set(cleaned)
    for code in list(cleaned):
        for implied in _ROLE_PORTAL_GRANTS.get(code, frozenset()):
            if implied in known and implied not in seen:
                seen.add(implied)
                granted.append(implied)
    if granted:
        cleaned = cleaned + granted
    prim = normalize_role_code(primary) if primary else cleaned[0]
    if not prim or prim not in cleaned:
        prim = cleaned[0]
    # primary را اول لیست نگه می‌داریم
    ordered = [prim] + [r for r in cleaned if r != prim]
    return prim, ordered


def user_matches_role_sql(role_code: str) -> ColumnElement[bool]:
    """شرط SQL: primary برابر نقش یا roles شامل آن نقش (با معادل‌های سازمانی)."""
    from sqlalchemy import cast
    from sqlalchemy.dialects.postgresql import JSONB as PG_JSONB

    from app.models.operational_models import User

    code = normalize_role_code(role_code)
    if not code:
        return User.role == "__never__"
    # نقش‌هایی که این نقش را implied می‌کنند (مثلاً faculty_1 → supervisor)
    equivalents = {code}
    for src, implied in _ROLE_IMPLIES.items():
        if code in implied:
            equivalents.add(src)
    ordered = sorted(equivalents)
    # Model JSONType=JSON → .contains() به LIKE (~~) تبدیل می‌شود و روی ستون
    # واقعی jsonb خطا می‌دهد: operator does not exist: jsonb ~~ text
    # Cast به JSONB تا عملگر @> استفاده شود (هم‌راستا با migration 039).
    return or_(
        User.role.in_(ordered),
        *[cast(User.roles, PG_JSONB).contains([c]) for c in ordered],
    )


def apply_roles_to_user(user: Any, roles: Sequence[str] | None, primary: str | None = None) -> None:
    """اعمال roles و role روی آبجکت User."""
    prim, ordered = sync_primary_and_roles(roles, primary=primary)
    user.role = prim
    user.roles = ordered
