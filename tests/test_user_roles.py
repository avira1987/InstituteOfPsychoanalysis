"""تست هلپر چندنقشهٔ کاربران."""

from types import SimpleNamespace

import pytest

from app.core.user_roles import (
    canonical_portal_role,
    normalize_user_roles,
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
