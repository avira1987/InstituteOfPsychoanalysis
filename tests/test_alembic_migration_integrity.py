"""یکپارچگی مایگریشن‌ها — جلوگیری از خطاهای استارت Docker (مثلاً FK ناسازگار)."""

from __future__ import annotations

from pathlib import Path


def test_migration_015_interviewer_user_id_matches_users_id_type():
    """users.id در 001 از نوع String(36) است؛ 015 نباید UUID بومی PostgreSQL بسازد."""
    path = (
        Path(__file__).resolve().parent.parent
        / "alembic"
        / "versions"
        / "015_interview_slot_interviewer_user.py"
    )
    src = path.read_text(encoding="utf-8")
    assert "sa.String(36)" in src, "interviewer_user_id باید String(36) باشد تا FK به users.id بخورد"
    assert "UUID(as_uuid=True)" not in src
    assert "postgresql.UUID" not in src


def test_portal_password_migrations_use_if_not_exists():
    """ALTER روی users فقط وقتی جدول وجود دارد معنا دارد؛ IF NOT EXISTS از خطای تکرار جلوگیری می‌کند."""
    versions = Path(__file__).resolve().parent.parent / "alembic" / "versions"
    for name in ("018_users_portal_password_plain.py", "019_ensure_portal_password_plain_column.py"):
        src = (versions / name).read_text(encoding="utf-8")
        assert "IF NOT EXISTS" in src, f"{name} باید ADD COLUMN IF NOT EXISTS داشته باشد"
