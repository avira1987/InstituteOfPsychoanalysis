"""مرجع صندوق پیگیری — بدون دیتابیس."""

from app.services.operator_reference_catalog import (
    build_reference_process_hints,
    build_reference_role_tasks,
)


def test_reference_role_tasks_excludes_student():
    rows = build_reference_role_tasks()
    codes = {r["role_code"] for r in rows}
    assert "student" not in codes
    assert any(r["role_code"] == "admin" for r in rows)
    admin = next(r for r in rows if r["role_code"] == "admin")
    assert len(admin["tasks"]) >= 1


def test_reference_process_hints_limited_and_has_roles():
    hints = build_reference_process_hints(50)
    assert len(hints) <= 50
    for h in hints:
        assert h["process_code"]
        assert h["roles_needed"]
        assert "student" not in h["roles_needed"]
