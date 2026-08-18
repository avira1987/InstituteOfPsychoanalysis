"""تست مسیر ورود پنل به ازای نقش — app/core/portal_role_home.py"""

from app.core.portal_role_home import (
    default_tasks_tab_for_role,
    portal_home_path,
    redirect_url_for_role,
)


def test_admin_redirects_to_panel_without_tab():
    assert redirect_url_for_role("admin") == "/panel"
    assert default_tasks_tab_for_role("admin") is None


def test_student_redirects_to_student_portal():
    assert redirect_url_for_role("student") == "/panel/portal/student"
    assert portal_home_path("student") == "/panel/portal/student"


def test_therapist_redirects_to_pending_tab():
    assert redirect_url_for_role("therapist") == "/panel/portal/therapist?tab=pending"
    assert default_tasks_tab_for_role("therapist") == "pending"


def test_supervisor_redirects_to_reviews_tab():
    assert redirect_url_for_role("supervisor") == "/panel/portal/supervisor?tab=reviews"
    assert default_tasks_tab_for_role("supervisor") == "reviews"


def test_staff_redirects_to_pending_tab():
    assert redirect_url_for_role("staff") == "/panel/portal/staff/admissions?tab=pending"
    assert portal_home_path("staff") == "/panel/portal/staff/admissions"


def test_internal_manager_redirects_like_staff():
    assert redirect_url_for_role("internal_manager") == "/panel/portal/staff/admissions?tab=pending"
    assert portal_home_path("internal_manager") == "/panel/portal/staff/admissions"


def test_site_manager_redirects_to_pending_tab():
    assert redirect_url_for_role("site_manager") == "/panel/portal/site-manager?tab=pending"


def test_interviewer_redirects_without_tab():
    assert redirect_url_for_role("interviewer") == "/panel/portal/interviewer"
    assert default_tasks_tab_for_role("interviewer") is None


def test_committee_roles_redirect_to_reviews_tab():
    expected = {
        "progress_committee": "/panel/portal/committee/progress?tab=reviews",
        "education_committee": "/panel/portal/committee/education?tab=reviews",
        "supervision_committee": "/panel/portal/committee/supervision?tab=reviews",
        "deputy_education": "/panel/portal/committee/education?tab=reviews",
        "monitoring_committee_officer": "/panel/portal/committee/supervision?tab=reviews",
    }
    for role, url in expected.items():
        assert redirect_url_for_role(role) == url


def test_finance_redirects_to_finance_dashboard():
    assert redirect_url_for_role("finance") == "/panel/finance"


def test_unknown_role_falls_back_to_panel():
    assert redirect_url_for_role("unknown_role") == "/panel"
    assert redirect_url_for_role(None) == "/panel"
