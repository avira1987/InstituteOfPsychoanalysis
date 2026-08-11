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
}


def _expanded_roles(have: set[str]) -> set[str]:
    out = set(have)
    for code in list(have):
        out |= _ROLE_IMPLIES.get(code, frozenset())
    return out


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
