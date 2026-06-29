"""Tests for film_observation_course_completion student final report form metadata."""

from __future__ import annotations

from app.api.process.routes import _file_upload_field_names_for_process
from app.meta.process_forms import get_process_forms
from app.meta.student_step_forms import filter_forms_for_student


def test_student_final_report_form_in_grades_entry():
    forms = get_process_forms("film_observation_course_completion", state_code="grades_entry")
    student_forms = filter_forms_for_student(forms)
    codes = {f.get("code") for f in student_forms}
    assert "film_observation_final_report_form" in codes
    assert "film_observation_grades_form" not in codes

    upload_form = next(f for f in student_forms if f.get("code") == "film_observation_final_report_form")
    field_names = [fld.get("name") for fld in upload_form.get("fields") or []]
    assert "final_report_pdf" in field_names


def test_final_report_pdf_allowed_for_upload_api():
    names = _file_upload_field_names_for_process(
        "film_observation_course_completion",
        state_code="grades_entry",
    )
    assert "final_report_pdf" in names
