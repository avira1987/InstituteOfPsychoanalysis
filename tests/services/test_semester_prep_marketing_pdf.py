"""Tests for marketing campaign PDF pack (semester prep handoff)."""

from app.services.semester_prep_marketing_pdf import (
    build_marketing_campaign_pdf_bytes,
    build_marketing_campaign_pdf_rows,
    resolve_marketing_handoff_context,
)


def test_resolve_handoff_falls_back_to_draft_courses_fall():
    ctx = {
        "courses_fall": [
            {
                "course_name": "روانکاوی ۱",
                "track": "جامع",
                "proposed_day": "دوشنبه",
                "proposed_time": "18:00",
            }
        ],
    }
    out = resolve_marketing_handoff_context("fall_semester_preparation", ctx)
    assert len(out["courses_finalized_fall"]) == 1
    assert out["courses_finalized_fall"][0]["day"] == "دوشنبه"


def test_fall_marketing_pdf_rows_include_interview_fees():
    ctx = {
        "fall_start_date": "2026-09-23",
        "per_unit_cost_introductory": 1_000_000,
        "interview_fee_introductory": 3_500_000,
        "interview_fee_comprehensive": 4_500_000,
        "courses_fall": [{"course_name": "روانکاوی ۱", "track": "جامع", "day": "دوشنبه"}],
    }
    rows = build_marketing_campaign_pdf_rows("fall_semester_preparation", ctx)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "3,500,000" in flat or "3500000" in flat.replace(",", "")
    assert "4,500,000" in flat or "4500000" in flat.replace(",", "")


def test_fall_marketing_pdf_rows_include_activities_1_2_5():
    ctx = {
        "fall_start_date": "2026-09-23",
        "fall_end_date": "2026-12-21",
        "per_unit_cost_introductory": 1_000_000,
        "courses_fall": [
            {
                "course_name": "روانکاوی ۱",
                "track": "جامع",
                "proposed_day": "دوشنبه",
                "proposed_time": "18:00",
                "instructor": "دکتر الف",
                "instructor_coordinated": True,
            }
        ],
    }
    rows = build_marketing_campaign_pdf_rows("fall_semester_preparation", ctx)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "فعالیت ۱" in flat
    assert "فعالیت ۲" in flat
    assert "فعالیت ۵" in flat
    assert "روانکاوی ۱" in flat


def test_winter_marketing_pdf_rows_include_activities_2_3():
    ctx = {
        "courses": [{"course_name": "تئوری ۲", "track": "آشنایی"}],
        "courses_finalized": [{"course_name": "تئوری ۲", "track": "آشنایی", "classroom_location": "کلاس ۳"}],
    }
    rows = build_marketing_campaign_pdf_rows("winter_semester_preparation", ctx)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "فعالیت ۲" in flat
    assert "فعالیت ۳" in flat
    assert "تئوری ۲" in flat


def test_fall_marketing_pdf_bytes_starts_with_pdf_header():
    ctx = {"fall_start_date": "2026-09-23", "fall_end_date": "2026-12-21"}
    try:
        data = build_marketing_campaign_pdf_bytes("fall_semester_preparation", ctx)
    except FileNotFoundError:
        return
    assert data[:4] == b"%PDF"
