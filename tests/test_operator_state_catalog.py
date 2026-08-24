"""کاتالوگ مراحل متادیتا و نگاشت نقش پورتال."""

import pytest

from app.meta import operator_state_catalog as osc
from app.meta.student_lifecycle_matrix import (
    get_panel_action_queue_for_role,
    get_panel_action_queue_for_roles,
)


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    osc.invalidate_caches()
    yield
    osc.invalidate_caches()


def test_normalize_admission_officer_typo():
    assert osc.normalize_assigned_role("admission_officer") == "admissions_officer"
    assert osc.normalize_assigned_role("admissions_officer") == "admissions_officer"


def test_therapist_catalog_non_empty():
    rows = osc.get_state_catalog_for_portal_role("therapist")
    assert len(rows) >= 1
    assert all(r.get("process_code") for r in rows)
    assert all(r.get("state_code") for r in rows)


def test_staff_includes_admissions_officer_states():
    """کارمند دفتر باید مراحل assigned_role مثل پذیرش را ببیند."""
    rows = osc.get_state_catalog_for_portal_role("staff")
    assigned = {r.get("assigned_role") for r in rows}
    assert "admissions_officer" in assigned


def test_internal_manager_catalog_matches_staff():
    staff_assigned = {r.get("assigned_role") for r in osc.get_state_catalog_for_portal_role("staff")}
    mgr_assigned = {r.get("assigned_role") for r in osc.get_state_catalog_for_portal_role("internal_manager")}
    assert mgr_assigned == staff_assigned
    assert "admissions_officer" in mgr_assigned


def test_finance_catalog_empty():
    assert osc.get_state_catalog_for_portal_role("finance") == []


def test_action_queue_therapist_has_state_definitions():
    out = get_panel_action_queue_for_role("therapist")
    assert out["schema_version"]
    kinds = [x.get("kind") for x in out["items"]]
    assert "role_pattern" in kinds
    assert "state_definition" in kinds
    assert out["stats"].get("state_definition_count", 0) >= 1


def test_action_queue_admin_has_many_state_definitions():
    out = get_panel_action_queue_for_role("admin")
    assert out["stats"].get("state_definition_count", 0) >= 10
    assert "state_definition" in [x.get("kind") for x in out["items"]]


def test_action_queue_for_roles_unions_therapist_and_interviewer():
    one = get_panel_action_queue_for_role("therapist")
    two = get_panel_action_queue_for_roles(["therapist", "interviewer"], primary="therapist")
    assert two["role"] == "therapist"
    one_states = {
        (i.get("process_code"), i.get("state_code"))
        for i in one["items"]
        if i.get("kind") == "state_definition"
    }
    two_states = {
        (i.get("process_code"), i.get("state_code"))
        for i in two["items"]
        if i.get("kind") == "state_definition"
    }
    assert one_states <= two_states
    assert two["stats"]["state_definition_count"] >= one["stats"]["state_definition_count"]
