"""تست واحد برای ثبت فرم مرحلهٔ اپراتور (فرایند ۲۹/۳۰ — آماده‌سازی ترم)."""

import pytest
from fastapi import HTTPException

from app.api.process.routes import _validate_semester_prep_interviewer_assignment_form
from app.meta.process_forms import get_process_forms
from app.meta.student_step_forms import (
    sanitize_operator_form_values,
    validate_operator_step_forms,
)
from app.services.semester_prep_service import semester_prep_interview_date_range_errors


def test_fall_calendar_form_requires_dates():
    """فرم تقویم پاییز فیلدهای الزامی تاریخ دارد؛ مقادیر خالی باید رد شود."""
    forms = get_process_forms("fall_semester_preparation", state_code="calendar_entry")
    assert forms, "academic_calendar_form باید برای calendar_entry تعریف شده باشد"

    ok, missing = validate_operator_step_forms(forms, {}, {})
    assert ok is False
    assert missing, "باید فیلدهای الزامی گزارش شود"


def test_fall_calendar_form_passes_with_required_values():
    forms = get_process_forms("fall_semester_preparation", state_code="calendar_entry")
    values = {
        "fall_start_date": "2026-09-23",
        "fall_end_date": "2026-12-21",
        "winter_start_date": "2026-12-22",
        "winter_end_date": "2027-03-20",
        "registration_payment_window_start": "2026-08-01",
        "registration_payment_window_end": "2026-09-01",
        "intern_interview_deadline_start": "2026-08-10",
        "intern_interview_deadline_end": "2026-08-15",
        "teaching_assistant_interview_deadline_start": "2026-08-15",
        "teaching_assistant_interview_deadline_end": "2026-08-20",
        "nowruz_holiday_start": "2027-03-21",
        "nowruz_holiday_end": "2027-04-02",
        # فیلدهای اختیاری بازه‌ای
        "fall_break_periods": [{"start": "2026-10-01", "end": "2026-10-03"}],
    }
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is True, f"باید معتبر باشد ولی نواقص: {missing}"


def test_fall_calendar_rejects_outlier_year():
    from app.services.semester_prep_service import semester_prep_calendar_date_errors

    errors = semester_prep_calendar_date_errors(
        {
            "fall_start_date": "2010-09-23",
            "fall_end_date": "2010-12-21",
            "winter_start_date": "2011-01-10",
            "winter_end_date": "2011-03-20",
            "registration_payment_window_start": "2010-08-01",
            "registration_payment_window_end": "2010-09-01",
            "intern_interview_deadline_start": "2010-08-10",
            "intern_interview_deadline_end": "2010-08-15",
            "teaching_assistant_interview_deadline_start": "2010-08-15",
            "teaching_assistant_interview_deadline_end": "2010-08-20",
            "nowruz_holiday_start": "2011-03-21",
            "nowruz_holiday_end": "2011-04-02",
        },
        today=__import__("datetime").date(2026, 7, 20),
    )
    assert errors
    assert any("سال" in e for e in errors)


def test_fall_calendar_rejects_winter_before_fall_end():
    from app.services.semester_prep_service import semester_prep_calendar_date_errors

    errors = semester_prep_calendar_date_errors(
        {
            "fall_start_date": "2026-09-23",
            "fall_end_date": "2026-12-21",
            "winter_start_date": "2026-11-01",
            "winter_end_date": "2027-03-20",
        },
        today=__import__("datetime").date(2026, 7, 20),
    )
    assert any("زمستان" in e and "پاییز" in e for e in errors)


def test_validate_semester_prep_calendar_form_raises():
    from app.api.process.routes import _validate_semester_prep_calendar_form

    with pytest.raises(HTTPException) as exc:
        _validate_semester_prep_calendar_form({"fall_start_date": "2010-01-01"})
    assert exc.value.status_code == 400


def test_interviewer_assignment_multi_select_required():
    """multi_select الزامی (مصاحبه‌کنندگان) باید لیست غیرخالی بخواهد."""
    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    assert forms
    ok, missing = validate_operator_step_forms(forms, {"comprehensive_interviewers": []}, {})
    assert ok is False
    assert missing


def test_interviewer_assignment_rejects_end_before_start():
    values = {
        "comprehensive_interviewers": ["u1"],
        "comprehensive_date_range_start": "2026-10-01",
        "comprehensive_date_range_end": "2026-09-01",
        "introductory_interviewers": ["u2"],
        "introductory_date_range_start": "2026-10-01",
        "introductory_date_range_end": "2026-10-15",
    }
    errors = semester_prep_interview_date_range_errors(values)
    assert len(errors) == 1
    assert "دوره جامع" in errors[0]

    with pytest.raises(HTTPException) as exc:
        _validate_semester_prep_interviewer_assignment_form(values)
    assert exc.value.status_code == 400


def test_interviewer_assignment_accepts_valid_date_ranges():
    values = {
        "comprehensive_interviewers": ["u1"],
        "comprehensive_date_range_start": "2026-10-01",
        "comprehensive_date_range_end": "2026-10-15",
        "introductory_interviewers": ["u2"],
        "introductory_date_range_start": "2026-10-01",
        "introductory_date_range_end": "2026-10-20",
    }
    assert semester_prep_interview_date_range_errors(values) == []
    _validate_semester_prep_interviewer_assignment_form(values)


def test_winter_interviewer_assignment_rejects_end_before_start():
    values = {
        "comprehensive_interviewers": ["u1"],
        "comprehensive_date_range_start": "2027-01-20",
        "comprehensive_date_range_end": "2027-01-10",
        "introductory_interviewers": ["u2"],
        "introductory_date_range_start": "2027-01-10",
        "introductory_date_range_end": "2027-01-25",
    }
    with pytest.raises(HTTPException) as exc:
        _validate_semester_prep_interviewer_assignment_form(values)
    assert exc.value.status_code == 400
    assert "دوره جامع" in str(exc.value.detail)


def test_sanitize_drops_unknown_keys():
    forms = get_process_forms("fall_semester_preparation", state_code="tuition_entry")
    raw = {
        "per_unit_cost_introductory": 1000,
        "per_unit_cost_comprehensive": 2000,
        "interview_fee_introductory": 500,
        "interview_fee_comprehensive": 600,
        "__internal": "secret",
        "not_a_field": "x",
    }
    cleaned = sanitize_operator_form_values(forms, raw)
    assert "__internal" not in cleaned
    assert "not_a_field" not in cleaned
    assert cleaned["per_unit_cost_introductory"] == 1000
    assert cleaned["interview_fee_introductory"] == 500


def test_marketing_campaign_requires_confirmation():
    forms = get_process_forms("fall_semester_preparation", state_code="marketing_campaign")
    assert forms, "marketing_campaign_form باید تعریف شده باشد"
    ok, missing = validate_operator_step_forms(forms, {}, {})
    assert ok is False
    assert missing
    ok2, _ = validate_operator_step_forms(
        forms,
        {"marketing_info_sent_to_manager": True},
        {},
    )
    assert ok2 is True


def test_fall_license_visible_if_new_number_when_changed():
    forms = get_process_forms("fall_semester_preparation", state_code="license_check")
    ok, _ = validate_operator_step_forms(forms, {"license_status": "بدون تغییر"}, {})
    assert ok is True
    from app.services.forms.condition import field_visible

    hidden = {"license_status": "بدون تغییر"}
    assert field_visible({"visible_if": {"license_status": "تغییر کرده"}}, hidden) is False
    shown = {"license_status": "تغییر کرده"}
    assert field_visible({"visible_if": {"license_status": "تغییر کرده"}}, shown) is True


def test_winter_license_visible_if_field_not_required_when_hidden():
    """new_license_number فقط وقتی license_status=تغییر کرده الزامی است (visible_if)."""
    forms = get_process_forms("winter_semester_preparation", state_code="license_check")
    assert forms
    # وضعیت «بدون تغییر» → فیلد شماره جدید لازم نیست.
    ok, _ = validate_operator_step_forms(forms, {"license_status": "بدون تغییر"}, {})
    assert ok is True


def test_fall_license_new_number_required_when_changed():
    forms = get_process_forms("fall_semester_preparation", state_code="license_check")
    ok, missing = validate_operator_step_forms(forms, {"license_status": "تغییر کرده"}, {})
    assert ok is False
    assert missing
    ok2, _ = validate_operator_step_forms(
        forms,
        {"license_status": "تغییر کرده", "new_license_number": "۱۲۳۴۵"},
        {},
    )
    assert ok2 is True


def test_winter_license_new_number_required_when_changed():
    forms = get_process_forms("winter_semester_preparation", state_code="license_check")
    ok, missing = validate_operator_step_forms(forms, {"license_status": "تغییر کرده"}, {})
    assert ok is False
    assert missing
    ok2, _ = validate_operator_step_forms(
        forms,
        {"license_status": "تغییر کرده", "new_license_number": "ABC-99"},
        {},
    )
    assert ok2 is True


def _interview_scheduling_base_values():
    return {}


def test_interview_scheduling_online_skips_location_field():
    forms = get_process_forms("fall_semester_preparation", state_code="interview_scheduling")
    values = {**_interview_scheduling_base_values(), "interview_mode": "آنلاین"}
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is True, missing


def test_interview_scheduling_in_person_requires_location():
    forms = get_process_forms("fall_semester_preparation", state_code="interview_scheduling")
    values = {**_interview_scheduling_base_values(), "interview_mode": "حضوری"}
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is False
    assert missing


def test_interview_scheduling_in_person_passes_with_location():
    forms = get_process_forms("fall_semester_preparation", state_code="interview_scheduling")
    values = {
        **_interview_scheduling_base_values(),
        "interview_mode": "حضوری",
        "interview_location_fa": "انستیتو روانکاوی تهران — سالن جلسات",
    }
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is True, missing


def test_winter_interview_scheduling_form_has_location_visible_if():
    forms = get_process_forms("winter_semester_preparation", state_code="interview_scheduling")
    scheduling_form = next(f for f in forms if f.get("code") == "winter_interview_scheduling_form")
    field_names = {fld.get("name") for fld in scheduling_form.get("fields") or []}
    assert "interview_location_fa" in field_names
    assert "interview_location_or_link" not in field_names


def test_winter_marketing_campaign_form_exists():
    forms = get_process_forms("winter_semester_preparation", state_code="marketing_campaign")
    codes = {f.get("code") for f in forms}
    assert "winter_marketing_campaign_form" in codes
    marketing_form = next(f for f in forms if f.get("code") == "winter_marketing_campaign_form")
    field_names = {fld.get("name") for fld in marketing_form.get("fields") or []}
    assert "marketing_info_sent_to_manager" in field_names


def test_winter_course_list_pre_filled_from_metadata():
    forms = get_process_forms("winter_semester_preparation", state_code="course_list_review")
    review_form = next(f for f in forms if f.get("code") == "winter_course_list_review_form")
    courses_field = next(
        fld for fld in review_form.get("fields") or [] if fld.get("name") == "courses"
    )
    assert courses_field.get("pre_filled_from") == "fall_semester_preparation.courses_winter"


def test_interviewer_assignment_options_source_metadata():
    forms = get_process_forms("fall_semester_preparation", state_code="interviewer_assignment")
    assignment_form = next(f for f in forms if f.get("code") == "interviewer_assignment_form")
    for name in ("comprehensive_interviewers", "introductory_interviewers"):
        field = next(fld for fld in assignment_form.get("fields") or [] if fld.get("name") == name)
        src = field.get("options_source") or {}
        assert src.get("type") == "users"
        # فقط استخر پیش‌آماده‌سازی (interviewer)
        assert src.get("roles") == ["interviewer"]
        assert src.get("is_active") is True
        assert field.get("creatable") is False


def test_course_list_form_roster_select_columns():
    forms = get_process_forms("fall_semester_preparation", state_code="course_list_creation")
    course_form = next(f for f in forms if f.get("code") == "course_list_form")
    fields = {fld.get("name"): fld for fld in course_form.get("fields") or []}
    assert "courses_fall" in fields
    assert "courses_winter" in fields
    assert fields["courses_fall"].get("label_fa") == "جدول دروس ترم پاییز"
    assert fields["courses_winter"].get("label_fa") == "جدول دروس ترم زمستان"
    assert fields["courses_fall"].get("allow_add_rows") is True
    assert fields["courses_fall"].get("allow_remove_rows") is True
    assert fields["courses_winter"].get("allow_add_rows") is True
    assert fields["courses_winter"].get("allow_remove_rows") is True

    courses_field = fields["courses_fall"]
    columns = {c.get("name"): c for c in courses_field.get("columns") or []}

    assert columns["course_name"].get("creatable") is True
    assert columns["course_name"].get("type") == "select"
    assert not columns["course_name"].get("auto_fill")
    assert columns["track"].get("creatable") is True
    assert columns["track"].get("auto_fill_from") == "course_name"
    assert not columns["instructor"].get("auto_fill")
    assert columns["instructor"].get("type") == "select"
    assert columns["instructor"].get("creatable") is True
    inst_src = columns["instructor"].get("options_source") or {}
    assert inst_src.get("kind") == "instructor"
    assert inst_src.get("filter_by_column") == "track"

    ta_src = columns["teaching_assistant"].get("options_source") or {}
    assert ta_src.get("kind") == "teaching_assistant"
    assert ta_src.get("filter_by_column") == "track"
    assert columns["teaching_assistant"].get("creatable") is True
    assert columns["teaching_assistant"].get("type") == "select"


def test_winter_course_list_review_roster_columns():
    forms = get_process_forms("winter_semester_preparation", state_code="course_list_review")
    review_form = next(f for f in forms if f.get("code") == "winter_course_list_review_form")
    courses_field = next(fld for fld in review_form.get("fields") or [] if fld.get("name") == "courses")
    assert courses_field.get("allow_add_rows") is True
    assert courses_field.get("allow_remove_rows") is True
    columns = {c.get("name"): c for c in courses_field.get("columns") or []}
    assert columns["course_name"].get("creatable") is True
    assert not columns["course_name"].get("auto_fill")
    assert columns["instructor"].get("type") == "select"
    assert columns["instructor"].get("creatable") is True
    assert columns["teaching_assistant"].get("type") == "select"
    assert columns["teaching_assistant"].get("creatable") is True
    assert (columns["teaching_assistant"].get("options_source") or {}).get("filter_by_column") == "track"


def test_educational_leave_committee_meeting_form_requires_datetime_and_mode():
    forms = get_process_forms("educational_leave", state_code="committee_review")
    assert forms, "leave_committee_meeting باید برای committee_review تعریف شده باشد"
    ok, missing = validate_operator_step_forms(forms, {}, {})
    assert ok is False
    assert missing
    ok2, missing2 = validate_operator_step_forms(
        forms,
        {
            "committee_meeting_at": "2026-09-15T10:30:00+00:00",
            "committee_meeting_mode": "in_person",
            "committee_meeting_location_fa": "سالن جلسات",
        },
        {},
    )
    assert ok2 is True, missing2
    ok3, _ = validate_operator_step_forms(
        forms,
        {
            "committee_meeting_at": "2026-09-15T10:30:00+00:00",
            "committee_meeting_mode": "online",
        },
        {},
    )
    assert ok3 is False


def test_educational_leave_deputy_alerted_uses_committee_review_form():
    forms = get_process_forms("educational_leave", state_code="deputy_alerted")
    codes = {f.get("code") for f in forms}
    assert "leave_committee_meeting" in codes


def test_educational_leave_return_confirmation_form():
    from app.meta.student_step_forms import validate_student_step_forms

    forms = get_process_forms("educational_leave", state_code="return_reminder_sent")
    assert forms
    ok, _ = validate_student_step_forms(forms, {}, {})
    assert ok is False
    ok2, missing2 = validate_student_step_forms(
        forms,
        {"return_registration_confirmed": True},
        {},
    )
    assert ok2 is True, missing2


def _course_finalization_row(*, coordinated: bool = False, location: str = ""):
    return {
        "course_name": "تئوری ۱",
        "track": "آشنایی",
        "day": "شنبه",
        "time": "10:00",
        "instructor": "دکتر نمونه",
        "teaching_assistant": "کمک‌مدرس نمونه",
        "classroom_location": location,
        "instructor_coordinated": coordinated,
    }


def test_fall_course_finalization_requires_day_and_time():
    forms = get_process_forms("fall_semester_preparation", state_code="course_finalization")
    fall_form = next(f for f in forms if f.get("code") == "course_finalization_form")
    day_col = next(
        c
        for f in fall_form["fields"]
        if f["name"] == "courses_finalized_fall"
        for c in f["columns"]
        if c["name"] == "day"
    )
    time_col = next(
        c
        for f in fall_form["fields"]
        if f["name"] == "courses_finalized_fall"
        for c in f["columns"]
        if c["name"] == "time"
    )
    assert day_col.get("auto_fill") is not True
    assert day_col.get("type") == "select"
    assert time_col.get("auto_fill") is not True

    row = _course_finalization_row(coordinated=True, location="")
    row["day"] = ""
    row["time"] = ""
    values = {
        "courses_finalized_fall": [row],
        "courses_finalized_winter": [_course_finalization_row(coordinated=True)],
    }
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is False
    assert any("روز" in m for m in missing)
    assert any("ساعت" in m for m in missing)


def test_fall_course_finalization_requires_coordination_not_location():
    forms = get_process_forms("fall_semester_preparation", state_code="course_finalization")
    assert forms
    row = _course_finalization_row()
    values = {
        "courses_finalized_fall": [row],
        "courses_finalized_winter": [row],
    }
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is False
    assert not any("مکان کلاس" in m for m in missing)
    assert any("هماهنگی با مدرس" in m for m in missing)


def test_fall_course_finalization_passes_without_location():
    forms = get_process_forms("fall_semester_preparation", state_code="course_finalization")
    row = _course_finalization_row(coordinated=True, location="")
    values = {
        "courses_finalized_fall": [row],
        "courses_finalized_winter": [row],
    }
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is True, missing


def test_fall_course_finalization_passes_when_complete():
    forms = get_process_forms("fall_semester_preparation", state_code="course_finalization")
    row = _course_finalization_row(coordinated=True, location="کلاس ۱ — طبقه دوم")
    values = {
        "courses_finalized_fall": [row],
        "courses_finalized_winter": [row],
    }
    ok, missing = validate_operator_step_forms(forms, values, {})
    assert ok is True, missing


def test_winter_course_finalization_requires_location_and_coordination():
    forms = get_process_forms("winter_semester_preparation", state_code="course_finalization")
    row = _course_finalization_row()
    ok, missing = validate_operator_step_forms(forms, {"courses_finalized": [row]}, {})
    assert ok is False
    assert any("مکان کلاس" in m for m in missing)
    assert any("هماهنگی با مدرس" in m for m in missing)
