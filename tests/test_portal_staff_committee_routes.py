"""Tests for staff/committee split routes and portal_role_home paths."""

from app.core.portal_role_home import (
    committee_kind_for_assigned_role,
    committee_kind_for_role,
    committee_kind_path,
    redirect_url_for_role,
    staff_lane_for_assigned_role,
    staff_lane_path,
)
from app.core.portal_role_nav import user_sees_nav_path


def test_staff_redirects_to_admissions_lane():
    assert redirect_url_for_role("staff") == "/panel/portal/staff/admissions?tab=pending"
    assert staff_lane_path() == "/panel/portal/staff/admissions"


def test_progress_committee_redirects_to_progress_kind():
    assert redirect_url_for_role("progress_committee") == (
        "/panel/portal/committee/progress?tab=reviews"
    )
    assert committee_kind_for_role("progress_committee") == "progress"


def test_deputy_education_redirects_to_education_kind():
    assert committee_kind_for_role("deputy_education") == "education"
    assert redirect_url_for_role("deputy_education").startswith("/panel/portal/committee/education")


def test_staff_lane_for_assigned_role():
    assert staff_lane_for_assigned_role("instructor") == "instruction"
    assert staff_lane_for_assigned_role("admissions_officer") == "admissions"
    assert staff_lane_for_assigned_role("therapy_education_coordinator") == "therapy-coord"


def test_committee_kind_for_assigned_role():
    assert committee_kind_for_assigned_role("supervision_committee") == "supervision"
    assert committee_kind_for_assigned_role("therapy_committee_chair") == "therapy"


def test_staff_cannot_see_admin_tools_in_nav():
    assert user_sees_nav_path("staff", "/panel/processes") is False
    assert user_sees_nav_path("staff", "/panel/audit") is False
    assert user_sees_nav_path("staff", staff_lane_path("admissions")) is True
    assert user_sees_nav_path("staff", committee_kind_path("progress")) is False


def test_therapist_sees_only_therapist_portal():
    assert user_sees_nav_path("therapist", "/panel/portal/therapist") is True
    assert user_sees_nav_path("therapist", staff_lane_path("admissions")) is False
    assert user_sees_nav_path("therapist", "/panel") is True
