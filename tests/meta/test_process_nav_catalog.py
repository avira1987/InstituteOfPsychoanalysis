"""کاتالوگ منوی سایدبار فرایندها."""

import pytest

from app.meta import operator_state_catalog as osc
from app.meta import process_nav_catalog as pnc


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    pnc.invalidate_caches()
    osc.invalidate_caches()
    yield
    pnc.invalidate_caches()
    osc.invalidate_caches()


def test_process_nav_path():
    assert pnc.process_nav_path("upgrade_to_ta") == "/panel/process-nav/upgrade_to_ta"


def test_therapist_process_nav_unique_codes():
    rows = pnc.get_process_nav_catalog_for_portal_role("therapist")
    codes = [r["process_code"] for r in rows]
    assert len(codes) == len(set(codes))
    assert len(rows) >= 1
    assert all(r.get("path", "").startswith("/panel/process-nav/") for r in rows)


def test_student_process_nav_includes_student_states():
    rows = pnc.get_process_nav_catalog_for_portal_role("student")
    codes = {r["process_code"] for r in rows}
    assert "educational_leave" in codes or "start_therapy" in codes
    assert all(r.get("primary_assigned_role") in ("student", "applicant") for r in rows)


def test_finance_process_nav_empty():
    assert pnc.get_process_nav_catalog_for_portal_role("finance") == []


def test_attach_pending_counts():
    catalog = [
        {"process_code": "foo", "label_fa": "Foo", "path": "/panel/process-nav/foo"},
        {"process_code": "bar", "label_fa": "Bar", "path": "/panel/process-nav/bar"},
    ]
    out = pnc.attach_pending_counts(catalog, {"foo": 3})
    assert out[0]["pending_count"] == 3
    assert out[1]["pending_count"] == 0


def test_admin_has_many_process_nav_items():
    rows = pnc.get_process_nav_catalog_for_portal_role("admin")
    assert len(rows) >= 10


def test_process_nav_catalog_onboarding_priority_order():
    rows = pnc.get_process_nav_catalog_for_portal_role("admin")
    codes = [r["process_code"] for r in rows]
    if "fall_semester_preparation" in codes and "therapy_changes" in codes:
        assert codes.index("fall_semester_preparation") < codes.index("therapy_changes")
    if "introductory_course_registration" in codes and "educational_leave" in codes:
        assert codes.index("introductory_course_registration") < codes.index("educational_leave")
    if "educational_leave" in codes and "therapy_changes" in codes:
        assert codes.index("educational_leave") < codes.index("therapy_changes")


def test_process_nav_catalog_includes_nav_tier():
    rows = pnc.get_process_nav_catalog_for_portal_role("admin")
    assert len(rows) >= 1
    for row in rows:
        assert row.get("nav_tier") in (0, 1, 2, 3)
    codes = {r["process_code"]: r["nav_tier"] for r in rows}
    if "fall_semester_preparation" in codes:
        assert codes["fall_semester_preparation"] == 0
    if "educational_leave" in codes:
        assert codes["educational_leave"] == 1
