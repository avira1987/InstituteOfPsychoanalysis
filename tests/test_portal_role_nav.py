"""Tests for portal_role_nav visibility rules."""

from app.core.portal_role_nav import ADMIN_ONLY_PATHS, user_sees_nav_path
from app.core.portal_role_home import committee_kind_path, staff_lane_path


def test_admin_sees_all_portal_paths():
    assert user_sees_nav_path("admin", "/panel/processes") is True
    assert user_sees_nav_path("admin", staff_lane_path("instruction")) is True
    assert user_sees_nav_path("admin", committee_kind_path("therapy")) is True
    assert user_sees_nav_path("admin", "/panel/portal/student") is True
    assert user_sees_nav_path("admin", "/panel/portal/therapist") is True
    assert user_sees_nav_path("admin", "/panel/portal/supervisor") is True
    assert user_sees_nav_path("admin", "/panel/portal/interviewer") is True
    assert user_sees_nav_path("admin", "/panel/portal/site-manager") is True


def test_interviewer_sees_admissions_lane_only():
    assert user_sees_nav_path("interviewer", staff_lane_path("admissions")) is True
    assert user_sees_nav_path("interviewer", staff_lane_path("instruction")) is False


def test_staff_sees_interviewer_portal_nav() -> None:
    assert user_sees_nav_path("staff", "/panel/portal/interviewer") is True


def test_internal_manager_sees_staff_lanes() -> None:
    assert user_sees_nav_path("internal_manager", staff_lane_path("admissions")) is True
    assert user_sees_nav_path("internal_manager", "/panel/portal/interviewer") is True
    assert user_sees_nav_path("internal_manager", "/panel/reports") is True


def test_specialist_lanes_for_named_roles() -> None:
    assert user_sees_nav_path("marketing", staff_lane_path("content-ops")) is True
    assert user_sees_nav_path("reference_center", staff_lane_path("content-ops")) is True
    assert user_sees_nav_path(
        "therapy_education_coordinator", staff_lane_path("therapy-coord")
    ) is True
    assert user_sees_nav_path("instructor", staff_lane_path("instruction")) is True
    assert user_sees_nav_path("marketing", staff_lane_path("admissions")) is False


def test_admin_only_paths_frozen():
    assert "/panel/rules" in ADMIN_ONLY_PATHS
    assert "/panel/dynamic-forms" in ADMIN_ONLY_PATHS
