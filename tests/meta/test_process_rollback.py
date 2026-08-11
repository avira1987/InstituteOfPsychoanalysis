"""Tests for rollback target resolution and student form unlock on rollback."""

from app.meta.process_rollback import resolve_rollback_target_from_history
from app.meta.student_step_forms import (
    CTX_EDIT_UNLOCK,
    CTX_SUBMITTED,
    apply_rollback_student_forms_to_context,
    is_state_locked_for_student,
)


def test_resolve_rollback_target_uses_last_operational_transition():
    history = [
        {"from_state": None, "to_state": "calendar_entry", "trigger_event": "start"},
        {"from_state": "calendar_entry", "to_state": "tuition_entry", "trigger_event": "calendar_submitted"},
    ]
    assert resolve_rollback_target_from_history(history, "tuition_entry") == "calendar_entry"


def test_resolve_rollback_target_skips_manual_rollback_for_chained_steps():
    history = [
        {"from_state": "interviewer_assignment", "to_state": "interview_scheduling", "trigger_event": "interviewers_assigned"},
        {"from_state": "interview_scheduling", "to_state": "published", "trigger_event": "interview_times_set"},
        {"from_state": "published", "to_state": "interview_scheduling", "trigger_event": "manual_rollback"},
    ]
    assert resolve_rollback_target_from_history(history, "interview_scheduling") == "interviewer_assignment"


def test_resolve_rollback_target_from_published():
    history = [
        {"from_state": "interview_scheduling", "to_state": "published", "trigger_event": "interview_times_set"},
    ]
    assert resolve_rollback_target_from_history(history, "published") == "interview_scheduling"


def test_resolve_rollback_target_none_at_initial_state():
    history = [
        {"from_state": None, "to_state": "calendar_entry", "trigger_event": "start"},
    ]
    assert resolve_rollback_target_from_history(history, "calendar_entry") is None


def test_rollback_unlocks_submitted_target_state_for_student_ui():
    """پس از بازگشت، فرم مرحلهٔ هدف دیگر برای دانشجو قفل نباشد."""
    ctx = {
        CTX_SUBMITTED: {
            "documents_upload": "2026-01-01T00:00:00+00:00",
            "documents_review": "2026-01-02T00:00:00+00:00",
        },
        CTX_EDIT_UNLOCK: {},
        "national_id_scan": {"file_name": "id.pdf"},
    }
    assert is_state_locked_for_student(ctx, "documents_upload") is True

    out = apply_rollback_student_forms_to_context(
        ctx,
        target_state="documents_upload",
        from_state="documents_review",
    )

    assert is_state_locked_for_student(out, "documents_upload") is False
    assert out[CTX_EDIT_UNLOCK].get("documents_upload") is True
    # مقادیر قبلی فرم حفظ می‌شود
    assert out["national_id_scan"]["file_name"] == "id.pdf"
    # ثبت مرحلهٔ ترک‌شده پاک می‌شود تا در ورود مجدد قفل نشود
    assert "documents_review" not in (out.get(CTX_SUBMITTED) or {})
    assert "documents_upload" in out[CTX_SUBMITTED]


def test_rollback_unlock_noop_when_target_never_submitted():
    ctx = {CTX_SUBMITTED: {}, CTX_EDIT_UNLOCK: {}}
    out = apply_rollback_student_forms_to_context(
        ctx,
        target_state="calendar_entry",
        from_state="tuition_entry",
    )
    assert is_state_locked_for_student(out, "calendar_entry") is False
    assert out[CTX_EDIT_UNLOCK].get("calendar_entry") is True


def test_reopen_student_step_forms_clears_lock_and_keys():
    from app.meta.student_step_forms import apply_reopen_student_step_forms_to_context

    ctx = {
        CTX_SUBMITTED: {"therapist_selection": "2026-01-01T00:00:00+00:00"},
        CTX_EDIT_UNLOCK: {},
        "therapist_id": "abc",
        "slot_ids": ["1", "2"],
        "weekly_sessions": 2,
    }
    assert is_state_locked_for_student(ctx, "therapist_selection") is True

    out = apply_reopen_student_step_forms_to_context(
        ctx,
        "therapist_selection",
        clear_keys=["therapist_id", "slot_ids", "weekly_sessions"],
    )

    assert is_state_locked_for_student(out, "therapist_selection") is False
    assert "therapist_selection" not in (out.get(CTX_SUBMITTED) or {})
    assert out[CTX_EDIT_UNLOCK].get("therapist_selection") is True
    assert "therapist_id" not in out
    assert "slot_ids" not in out
    assert "weekly_sessions" not in out
