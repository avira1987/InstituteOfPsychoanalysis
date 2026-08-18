"""SOP catalog prefill and unit-based tuition for registration/gateway."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

from app.models.operational_models import ProcessInstance
from app.services.course_committee_roster_service import (
    build_sop_curriculum_draft_rows,
    catalog_units_for_course,
    reload_catalog_cache,
)
from app.services.semester_prep_service import (
    _build_courses_finalized_from_draft,
    _prefill_course_table_from_sop_or_roster,
)
from app.services.term_course_offering_service import resolve_registration_fees
from app.services.tuition_installment_service import (
    refresh_instance_tuition_context,
    resolve_expected_payable_rial,
)


@pytest.fixture(autouse=True)
def _fresh_catalog():
    reload_catalog_cache()
    yield
    reload_catalog_cache()


def test_sop_prefill_fall_and_winter_include_units():
    fall = build_sop_curriculum_draft_rows(1)
    winter = build_sop_curriculum_draft_rows(2)
    assert fall, "ترم ۱ باید از کاتالوگ SOP پر شود"
    assert winter, "ترم ۲ باید از کاتالوگ SOP پر شود"

    psycho1 = next(
        (r for r in fall if r.get("course_code") == "theory_psychoanalysis_1"
         or "روانکاوی ۱" in str(r.get("course_name") or "")),
        None,
    )
    assert psycho1 is not None
    assert int(psycho1.get("units") or 0) == 2
    assert catalog_units_for_course("theory_psychoanalysis_1") == 2

    filled = _prefill_course_table_from_sop_or_roster(None, [], curriculum_term=1)
    assert len(filled) == len(fall)
    assert any(int(r.get("units") or 0) == 2 for r in filled)

    # جدول غیرخالی بازنویسی نشود
    custom = [{"course_name": "درس سفارشی", "units": 9}]
    kept = _prefill_course_table_from_sop_or_roster(custom, [], curriculum_term=1)
    assert len(kept) == 1
    assert kept[0]["course_name"] == "درس سفارشی"


def test_finalized_rows_carry_units_from_draft():
    draft = [
        {
            "course_name": "تئوری روانکاوی ۱",
            "course_code": "theory_psychoanalysis_1",
            "units": 2,
            "day": "شنبه",
            "time": "09:00",
            "instructor": "مدرس",
        }
    ]
    finalized = _build_courses_finalized_from_draft(draft)
    assert finalized
    assert int(finalized[0].get("units") or 0) == 2


def test_finalized_rows_skip_blank_placeholder_rows():
    draft = [
        {
            "course_name": "تئوری روانکاوی ۱",
            "proposed_day": "شنبه",
            "proposed_time": "18:00",
            "instructor": "مدرس",
        },
        {
            "course_name": "",
            "proposed_day": "",
            "instructor": "",
        },
        {"course_name": "   "},
    ]
    finalized = _build_courses_finalized_from_draft(draft)
    assert finalized is not None
    assert len(finalized) == 1
    assert finalized[0]["course_name"] == "تئوری روانکاوی ۱"
    assert finalized[0]["instructor"] == "مدرس"


@pytest.mark.asyncio
async def test_resolve_registration_fees_sums_units_times_per_unit(db_session):
    """دو درس ۲ و ۳ واحدی با هزینه هر واحد مشخص → جمع درست."""
    per_unit = 1_000_000  # ریال
    ctx = {
        "selected_courses": ["theory_psychoanalysis_1", "theory_technique_1"],
    }
    # theory_psychoanalysis_1 = 2, theory_technique_1 = 3 (از کاتالوگ)
    assert catalog_units_for_course("theory_psychoanalysis_1") == 2
    assert catalog_units_for_course("theory_technique_1") == 3

    with patch(
        "app.services.term_course_offering_service.get_active_calendar",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.term_course_offering_service.get_term_tuition_from_calendar",
        return_value={"per_unit_cost_introductory": per_unit},
    ), patch(
        "app.services.financial_program_defaults_service.get_effective_financial_program_defaults",
        new=AsyncMock(
            return_value={
                "interview_fee_introductory": 5_000_000,
                "per_unit_cost_introductory": per_unit,
                "registration_interview_fee_rial": 5_000_000,
                "registration_tuition_invoice_toman": 100_000,
            }
        ),
    ):
        fees = await resolve_registration_fees(
            db_session,
            "introductory_course_registration",
            ctx,
            "course_selection",
        )

    expected = (2 + 3) * per_unit
    assert fees["tuition_total_rial"] == expected
    assert len(fees["tuition_lines"]) == 2
    by_code = {line["course_code"]: line for line in fees["tuition_lines"]}
    assert by_code["theory_psychoanalysis_1"]["units"] == 2
    assert by_code["theory_psychoanalysis_1"]["line_amount_rial"] == 2 * per_unit
    assert by_code["theory_technique_1"]["units"] == 3
    assert by_code["theory_technique_1"]["line_amount_rial"] == 3 * per_unit


@pytest.mark.asyncio
async def test_changing_selected_courses_updates_stored_tuition(db_session):
    per_unit = 2_000_000

    async def _fees_for(selected):
        with patch(
            "app.services.term_course_offering_service.get_active_calendar",
            new=AsyncMock(return_value=None),
        ), patch(
            "app.services.term_course_offering_service.get_term_tuition_from_calendar",
            return_value={"per_unit_cost_introductory": per_unit},
        ), patch(
            "app.services.financial_program_defaults_service.get_effective_financial_program_defaults",
            new=AsyncMock(
                return_value={
                    "interview_fee_introductory": 5_000_000,
                    "per_unit_cost_introductory": per_unit,
                    "registration_interview_fee_rial": 5_000_000,
                    "registration_tuition_invoice_toman": 50_000,
                }
            ),
        ), patch(
            "app.services.installment_settings_service.get_installment_policy",
            new=AsyncMock(return_value={"term2_installment_gap_days": 25}),
        ):
            return await refresh_instance_tuition_context(
                db_session,
                "introductory_course_registration",
                "course_selection",
                {
                    "selected_courses": selected,
                    # مبلغ قدیمی ذخیره‌شده که باید بازنویسی شود
                    "tuition_total_rial": 999,
                    "tuition_amount_rial": 999,
                    "payable_amount_rial": 999,
                    "payment_amount_rial": 999,
                },
            )

    ctx1 = await _fees_for(["theory_psychoanalysis_1"])
    assert ctx1["tuition_total_rial"] == 2 * per_unit

    ctx2 = await _fees_for(["theory_psychoanalysis_1", "theory_technique_1"])
    assert ctx2["tuition_total_rial"] == (2 + 3) * per_unit
    assert ctx2["tuition_total_rial"] != 999
    assert ctx2["payable_amount_rial"] == ctx2["tuition_total_rial"] or ctx2.get(
        "payment_amount_rial"
    ) == ctx2["tuition_total_rial"]


@pytest.mark.asyncio
async def test_resolve_expected_payable_matches_unit_total(db_session):
    from app.services.institute_operational_anchor import ensure_institute_operational_student

    per_unit = 1_500_000
    expected = (2 + 3) * per_unit
    anchor = await ensure_institute_operational_student(db_session)
    now = datetime.now(timezone.utc)
    instance = ProcessInstance(
        id=uuid.uuid4(),
        student_id=anchor.id,
        process_code="introductory_course_registration",
        current_state_code="payment",
        is_completed=False,
        is_cancelled=False,
        started_at=now,
        context_data={
            "selected_courses": ["theory_psychoanalysis_1", "theory_technique_1"],
            "tuition_total_rial": 111,  # stale
            "payment_method": "full",
        },
    )
    db_session.add(instance)
    await db_session.flush()

    with patch(
        "app.services.term_course_offering_service.get_active_calendar",
        new=AsyncMock(return_value=None),
    ), patch(
        "app.services.term_course_offering_service.get_term_tuition_from_calendar",
        return_value={"per_unit_cost_introductory": per_unit},
    ), patch(
        "app.services.financial_program_defaults_service.get_effective_financial_program_defaults",
        new=AsyncMock(
            return_value={
                "interview_fee_introductory": 5_000_000,
                "per_unit_cost_introductory": per_unit,
                "registration_interview_fee_rial": 5_000_000,
                "registration_tuition_invoice_toman": 50_000,
            }
        ),
    ), patch(
        "app.services.installment_settings_service.get_installment_policy",
        new=AsyncMock(return_value={"term2_installment_gap_days": 25}),
    ):
        payable = await resolve_expected_payable_rial(db_session, instance)

    assert payable == expected
