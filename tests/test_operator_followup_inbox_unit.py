"""تست واحد منطق صندوق پیگیری اپراتور — بدون وابستگی به دیتابیس."""

import pytest

from app.services.operator_followup_inbox import _resolve_process_item


@pytest.mark.parametrize(
    "assigned,state,expect_none",
    [
        ("student", "anything", True),
        ("STUDENT", "x", True),
        ("applicant", "x", True),
        ("system", "x", True),
    ],
)
def test_resolve_excludes_queue_roles(assigned, state, expect_none):
    r = _resolve_process_item(assigned, state, False)
    assert (r is None) == expect_none


def test_resolve_uses_explicit_role():
    r = _resolve_process_item("instructor", "lesson_done", False)
    assert r is not None
    code, label, uncertain = r
    assert code == "instructor"
    assert "مدرس" in label
    assert uncertain is False


def test_resolve_fallback_staff_keyword():
    r = _resolve_process_item(None, "staff_review_pending", False)
    assert r is not None
    code, label, _u = r
    assert code == "staff"
    assert "کارمند" in label
