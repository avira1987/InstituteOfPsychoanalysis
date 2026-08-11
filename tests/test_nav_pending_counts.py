"""تست شمارش کارهای منتظر منوی کناری — app/services/nav_pending_counts.py"""

from app.services.nav_pending_counts import _waiting_staff


def test_waiting_staff_counts_documents_review():
    assert _waiting_staff("documents_review") is True


def test_waiting_staff_excludes_student_document_turn_states():
    assert _waiting_staff("documents_upload") is False
    assert _waiting_staff("documents_incomplete") is False


def test_waiting_staff_still_counts_legacy_staff_states():
    assert _waiting_staff("staff_review") is True
    assert _waiting_staff("payment_verification") is True
    assert _waiting_staff("document_check") is True

