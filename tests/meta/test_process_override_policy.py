"""Unit tests for process override / rollback / restart staff policy."""

from app.meta.process_override_policy import (
    OVERRIDE_ROLES,
    actor_role_can_override,
    can_actor_rollback_process,
    user_can_override_process,
    validate_override_reason,
)
from app.meta.process_restart_policy import RESTART_STAFF_ROLES, can_actor_restart_process


def test_override_roles_exclude_staff():
    assert "staff" not in OVERRIDE_ROLES
    assert "admin" in OVERRIDE_ROLES
    assert "deputy_education" in OVERRIDE_ROLES
    assert RESTART_STAFF_ROLES == OVERRIDE_ROLES


def test_actor_role_can_override():
    assert actor_role_can_override("admin") is True
    assert actor_role_can_override("deputy_education") is True
    assert actor_role_can_override("deputy_education_director") is True
    assert actor_role_can_override("staff") is False
    assert actor_role_can_override("course_committee") is False


def test_can_actor_rollback_process():
    ok, _ = can_actor_rollback_process(actor_role="admin")
    assert ok is True
    ok, msg = can_actor_rollback_process(actor_role="staff")
    assert ok is False
    assert "مجوز" in msg


def test_can_actor_restart_staff_denied():
    ok, msg = can_actor_restart_process(
        actor_role="staff",
        process_code="extra_session",
        is_own_instance=False,
    )
    assert ok is False
    assert "مجوز" in msg


def test_can_actor_restart_deputy_ok():
    ok, _ = can_actor_restart_process(
        actor_role="deputy_education",
        process_code="fall_semester_preparation",
        is_own_instance=False,
    )
    assert ok is True


def test_validate_override_reason():
    ok, _ = validate_override_reason("کافی است", actor_role="admin")
    assert ok is True
    ok, msg = validate_override_reason("  ", actor_role="admin")
    assert ok is False
    assert "دلیل" in msg
    ok, _ = validate_override_reason(None, actor_role="student")
    assert ok is True


def test_user_can_override_process_multi_role():
    class U:
        role = "staff"
        roles = ["staff", "deputy_education"]

    assert user_can_override_process(U()) is True

    class StaffOnly:
        role = "staff"
        roles = ["staff"]

    assert user_can_override_process(StaffOnly()) is False
