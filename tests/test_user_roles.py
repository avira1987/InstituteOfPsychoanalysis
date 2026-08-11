"""تست هلپر چندنقشهٔ کاربران."""

from types import SimpleNamespace

import pytest

from app.core.user_roles import (
    normalize_user_roles,
    primary_role,
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


def test_sync_rejects_empty():
    with pytest.raises(ValueError):
        sync_primary_and_roles([])


def test_primary_role_helper():
    u = SimpleNamespace(role="staff", roles=["therapist", "staff"])
    assert primary_role(u) == "staff"
