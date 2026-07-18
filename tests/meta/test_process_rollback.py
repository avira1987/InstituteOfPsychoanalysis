"""Tests for rollback target resolution."""

from app.meta.process_rollback import resolve_rollback_target_from_history


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
