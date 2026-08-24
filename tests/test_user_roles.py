"""تست هلپر چندنقشهٔ کاربران."""

from types import SimpleNamespace

import pytest

from app.core.user_roles import (
    candidate_actor_roles,
    canonical_portal_role,
    expanded_user_roles,
    normalize_user_roles,
    operator_portal_roles,
    ordered_actor_roles,
    primary_role,
    role_grants,
    sync_primary_and_roles,
    user_has_role,
)


def test_normalize_falls_back_to_primary():
    u = SimpleNamespace(role="therapist", roles=None)
    assert normalize_user_roles(u) == ["therapist"]


def test_normalize_keeps_list_and_injects_primary():
    u = SimpleNamespace(role="therapist", roles=["supervisor"])
    assert normalize_user_roles(u) == ["therapist", "supervisor"]


def test_user_has_role_any_membership():
    u = SimpleNamespace(role="therapist", roles=["therapist", "supervisor"])
    assert user_has_role(u, "supervisor", admin_bypass=False)
    assert user_has_role(u, "finance", admin_bypass=False) is False
    assert user_has_role(u, "finance", admin_bypass=True) is False


def test_admin_bypass():
    u = SimpleNamespace(role="admin", roles=["admin", "staff"])
    assert user_has_role(u, "finance", admin_bypass=True)
    assert user_has_role(u, "finance", admin_bypass=False) is False


def test_sync_primary_must_be_in_roles():
    prim, roles = sync_primary_and_roles(["therapist", "supervisor"], primary="supervisor")
    assert prim == "supervisor"
    assert roles[0] == "supervisor"
    assert set(roles) == {"therapist", "supervisor"}


def test_internal_manager_implies_staff():
    u = SimpleNamespace(role="internal_manager", roles=["internal_manager"])
    assert user_has_role(u, "staff", admin_bypass=False)
    assert user_has_role(u, "finance", admin_bypass=False) is False


def test_sync_faculty_1_grants_interviewer_supervisor():
    prim, roles = sync_primary_and_roles(["faculty_1"], primary="faculty_1")
    assert prim == "faculty_1"
    assert "interviewer" in roles
    assert "supervisor" in roles


def test_sync_educational_instructor_grants_instructor():
    prim, roles = sync_primary_and_roles(
        ["educational_instructor"], primary="educational_instructor"
    )
    assert prim == "educational_instructor"
    assert "instructor" in roles


def test_sync_rejects_empty():
    with pytest.raises(ValueError):
        sync_primary_and_roles([])


def test_primary_role_helper():
    u = SimpleNamespace(role="staff", roles=["therapist", "staff"])
    assert primary_role(u) == "staff"


def test_canonical_portal_role_internal_manager():
    assert canonical_portal_role("internal_manager") == "staff"
    assert canonical_portal_role("staff") == "staff"


def test_faculty_1_implies_interviewer():
    u = SimpleNamespace(role="faculty_1", roles=["faculty_1"])
    assert user_has_role(u, "interviewer", admin_bypass=False)
    assert user_has_role(u, "supervisor", admin_bypass=False)
    assert user_has_role(u, "staff", admin_bypass=False) is False
    assert role_grants("faculty_1", "interviewer")
    assert role_grants("faculty_1", "staff") is False
    assert role_grants("interviewer", "interviewer")


def test_expanded_and_ordered_actor_roles_faculty_1():
    u = SimpleNamespace(role="faculty_1", roles=["faculty_1"])
    expanded = expanded_user_roles(u)
    assert expanded == {"faculty_1", "supervisor", "interviewer"}
    ordered = ordered_actor_roles(u)
    assert ordered[0] == "faculty_1"
    assert "supervisor" in ordered
    assert "interviewer" in ordered


def test_ordered_actor_roles_educational_instructor():
    u = SimpleNamespace(role="educational_instructor", roles=["educational_instructor"])
    assert ordered_actor_roles(u)[0] == "educational_instructor"
    assert "instructor" in ordered_actor_roles(u)
    assert "instructor" in expanded_user_roles(u)


def test_ordered_actor_roles_dual_therapist_interviewer():
    u = SimpleNamespace(role="therapist", roles=["therapist", "interviewer"])
    ordered = ordered_actor_roles(u)
    assert ordered[0] == "therapist"
    assert "interviewer" in ordered
    assert expanded_user_roles(u) == {"therapist", "interviewer"}


def test_candidate_actor_roles_system_not_expanded():
    u = SimpleNamespace(role="staff", roles=["staff"])
    assert candidate_actor_roles("system", u) == ["system"]
    assert candidate_actor_roles("student", None) == ["student"]


def test_operator_portal_roles_faculty_1():
    u = SimpleNamespace(role="faculty_1", roles=["faculty_1"])
    roles = operator_portal_roles(u)
    assert roles[0] == "faculty_1"
    assert "supervisor" in roles
    assert "interviewer" in roles


def test_operator_portal_roles_dual_therapist_interviewer():
    u = SimpleNamespace(role="therapist", roles=["therapist", "interviewer"])
    roles = operator_portal_roles(u)
    assert "therapist" in roles
    assert "interviewer" in roles


def test_operator_portal_roles_student_empty():
    u = SimpleNamespace(role="student", roles=["student"])
    assert operator_portal_roles(u) == []
