"""Tests for portal_role_nav visibility rules."""

from app.core.portal_role_nav import ADMIN_ONLY_PATHS, user_sees_nav_path
from app.core.portal_role_home import committee_kind_path, staff_lane_path


def test_admin_sees_all_portal_paths():
    assert user_sees_nav_path("admin", "/panel/processes") is True
    assert user_sees_nav_path("admin", staff_lane_path("instruction")) is True
    assert user_sees_nav_path("admin", committee_kind_path("therapy")) is True


def test_interviewer_sees_admissions_lane_only():
    assert user_sees_nav_path("interviewer", staff_lane_path("admissions")) is True
    assert user_sees_nav_path("interviewer", staff_lane_path("instruction")) is False


def test_staff_sees_interviewer_portal_nav() -> None:
    assert user_sees_nav_path("staff", "/panel/portal/interviewer") is True


def test_admin_only_paths_frozen():
    assert "/panel/rules" in ADMIN_ONLY_PATHS
    assert "/panel/dynamic-forms" in ADMIN_ONLY_PATHS
