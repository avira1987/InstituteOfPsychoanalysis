"""شهریه دوره آشنایی = مجموع واحد انتخاب‌شده × نرخ پنل مالی (ریال)."""

from __future__ import annotations

import uuid
from contextlib import ExitStack
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.models.operational_models import ProcessInstance
from app.services.course_committee_roster_service import catalog_units_for_course
from app.services.term_course_offering_service import (
    extract_course_codes,
    resolve_registration_fees,
    selected_course_codes_for_tuition,
)
from app.services.tuition_installment_service import (
    apply_tuition_payment_context,
    refresh_instance_tuition_context,
    resolve_expected_payable_rial,
)

# همان سناریوی گزارش‌شده: ۷ واحد × ۱۰٬۰۰۰ ریال = ۷۰٬۰۰۰ — نه فاکتور پشتیبان ۵۲٬۰۰۰
PER_UNIT = 10_000
BACKUP_INVOICE_TOMAN = 5_200  # اگر واحد×نرخ شکست بخورد → ۵۲٬۰۰۰ ریال
SEVEN_UNIT_COURSES = [
    "theory_psychoanalysis_1",  # 2
    "theory_technique_1",  # 3
    "skills_practice_1",  # 2
]
SEVEN_UNIT_TOTAL = 7 * PER_UNIT


def _fd(per_unit=PER_UNIT, invoice_toman=BACKUP_INVOICE_TOMAN):
    return {
        "interview_fee_introductory": 5_000_000,
        "per_unit_cost_introductory": per_unit,
        "registration_interview_fee_rial": 5_000_000,
        "registration_tuition_invoice_toman": invoice_toman,
    }


def _patches(per_unit=PER_UNIT, invoice_toman=BACKUP_INVOICE_TOMAN, calendar=None, offerings=None):
    kw = dict(
        return_value={"per_unit_cost_introductory": per_unit},
    )
    if offerings is not None:
        list_off = AsyncMock(return_value=offerings)
    else:
        list_off = AsyncMock(return_value=[])
    return (
        patch(
            "app.services.term_course_offering_service.get_active_calendar",
            new=AsyncMock(return_value=calendar),
        ),
        patch(
            "app.services.term_course_offering_service.get_term_tuition_from_calendar",
            **kw,
        ),
        patch(
            "app.services.financial_program_defaults_service.get_effective_financial_program_defaults",
            new=AsyncMock(return_value=_fd(per_unit, invoice_toman)),
        ),
        patch(
            "app.services.term_course_offering_service.list_offerings",
            new=list_off,
        ),
        patch(
            "app.services.installment_settings_service.get_installment_policy",
            new=AsyncMock(return_value={"term2_installment_gap_days": 25}),
        ),
    )


def test_catalog_seven_units_for_reported_intro_bundle():
    assert catalog_units_for_course("theory_psychoanalysis_1") == 2
    assert catalog_units_for_course("theory_technique_1") == 3
    assert catalog_units_for_course("skills_practice_1") == 2
    assert sum(catalog_units_for_course(c) for c in SEVEN_UNIT_COURSES) == 7


def test_extract_course_codes_csv_json_and_dicts():
    assert extract_course_codes("theory_psychoanalysis_1,theory_technique_1,skills_practice_1") == SEVEN_UNIT_COURSES
    assert extract_course_codes(
        '["theory_psychoanalysis_1","theory_technique_1","skills_practice_1"]'
    ) == SEVEN_UNIT_COURSES
    assert extract_course_codes(
        [{"value": c} for c in SEVEN_UNIT_COURSES]
    ) == SEVEN_UNIT_COURSES
    assert extract_course_codes("theory_1,theory_technique_1") == [
        "theory_psychoanalysis_1",
        "theory_technique_1",
    ]


def test_intro_term1_does_not_treat_catalog_as_selection():
    ctx = {
        "available_courses": SEVEN_UNIT_COURSES + ["film_observation_1"],
        "selected_courses": SEVEN_UNIT_COURSES,
    }
    assert selected_course_codes_for_tuition("introductory_course_registration", ctx) == SEVEN_UNIT_COURSES
    assert selected_course_codes_for_tuition(
        "introductory_course_registration",
        {"available_courses": SEVEN_UNIT_COURSES},
    ) == []


def test_intro_term2_uses_available_courses_field():
    assert selected_course_codes_for_tuition(
        "intro_second_semester_registration",
        {"available_courses": SEVEN_UNIT_COURSES},
    ) == SEVEN_UNIT_COURSES


@pytest.mark.asyncio
async def test_seven_units_cash_payable_is_70000_not_52000(db_session):
    ctx = {
        "selected_courses": SEVEN_UNIT_COURSES,
        "payment_method": "cash",
        "payment_amount_rial": 52_000,  # مانده هزینه مصاحبه / فاکتور اشتباه
    }
    patches = _patches()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        fees = await resolve_registration_fees(
            db_session,
            "introductory_course_registration",
            ctx,
            "payment",
        )
        refreshed = await refresh_instance_tuition_context(
            db_session,
            "introductory_course_registration",
            "payment",
            ctx,
        )

    assert fees["tuition_total_rial"] == SEVEN_UNIT_TOTAL
    assert fees["tuition_total_rial"] != BACKUP_INVOICE_TOMAN * 10
    assert sum(line["units"] for line in fees["tuition_lines"]) == 7
    for line in fees["tuition_lines"]:
        assert line["per_unit_cost_rial"] == PER_UNIT
        assert line["line_amount_rial"] == line["units"] * PER_UNIT
    assert refreshed["payable_amount_rial"] == SEVEN_UNIT_TOTAL
    assert refreshed["payment_amount_rial"] == SEVEN_UNIT_TOTAL
    assert refreshed["tuition_total_rial"] == SEVEN_UNIT_TOTAL


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "selected",
    [
        SEVEN_UNIT_COURSES,
        ",".join(SEVEN_UNIT_COURSES),
        '["theory_psychoanalysis_1","theory_technique_1","skills_practice_1"]',
        [{"value": c} for c in SEVEN_UNIT_COURSES],
        [{"code": c} for c in SEVEN_UNIT_COURSES],
    ],
)
async def test_selected_courses_payload_shapes_all_bill_70000(db_session, selected):
    patches = _patches()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        fees = await resolve_registration_fees(
            db_session,
            "introductory_course_registration",
            {"selected_courses": selected},
            "payment",
        )
    assert fees["tuition_total_rial"] == SEVEN_UNIT_TOTAL


@pytest.mark.asyncio
async def test_term2_available_courses_field_bills_units(db_session):
    patches = _patches()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        fees = await resolve_registration_fees(
            db_session,
            "intro_second_semester_registration",
            {"available_courses": SEVEN_UNIT_COURSES},
            "payment_processing",
        )
    assert fees["tuition_total_rial"] == SEVEN_UNIT_TOTAL


@pytest.mark.asyncio
async def test_live_panel_rate_wins_over_stale_offering_rate(db_session):
    offerings = [
        SimpleNamespace(
            course_code="theory_psychoanalysis_1",
            units=2,
            per_unit_cost_rial=1,  # نرخ کهنه روی ارائه
            course_name_fa="تئوری روانکاوی ۱",
        ),
        SimpleNamespace(
            course_code="theory_technique_1",
            units=3,
            per_unit_cost_rial=1,
            course_name_fa="تئوری تکنیک‌ها ۱",
        ),
        SimpleNamespace(
            course_code="skills_practice_1",
            units=2,
            per_unit_cost_rial=1,
            course_name_fa="تکنیک ۱",
        ),
    ]
    cal = SimpleNamespace(term_code="1404-1", extra_data={})
    patches = _patches(offerings=offerings, calendar=cal)
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        fees = await resolve_registration_fees(
            db_session,
            "introductory_course_registration",
            {"selected_courses": SEVEN_UNIT_COURSES},
            "payment",
        )
    assert fees["tuition_total_rial"] == SEVEN_UNIT_TOTAL
    assert all(line["per_unit_cost_rial"] == PER_UNIT for line in fees["tuition_lines"])


@pytest.mark.asyncio
async def test_offering_zero_units_falls_back_to_catalog(db_session):
    offerings = [
        SimpleNamespace(
            course_code="theory_psychoanalysis_1",
            units=0,
            per_unit_cost_rial=PER_UNIT,
            course_name_fa="تئوری روانکاوی ۱",
        ),
    ]
    cal = SimpleNamespace(term_code="1404-1", extra_data={})
    patches = _patches(offerings=offerings, calendar=cal)
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        fees = await resolve_registration_fees(
            db_session,
            "introductory_course_registration",
            {"selected_courses": ["theory_psychoanalysis_1"]},
            "course_selection",
        )
    assert fees["tuition_lines"][0]["units"] == 2
    assert fees["tuition_total_rial"] == 2 * PER_UNIT


@pytest.mark.asyncio
async def test_option_units_used_when_offering_missing(db_session):
    ctx = {
        "selected_courses": ["custom_elective"],
        "available_course_options": [
            {"value": "custom_elective", "label_fa": "درس سفارشی", "units": 7},
        ],
    }
    patches = _patches()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        fees = await resolve_registration_fees(
            db_session,
            "introductory_course_registration",
            ctx,
            "payment",
        )
    assert fees["tuition_total_rial"] == 7 * PER_UNIT
    assert fees["tuition_lines"][0]["units"] == 7


@pytest.mark.asyncio
async def test_gateway_expected_payable_matches_unit_total(db_session):
    from app.services.institute_operational_anchor import ensure_institute_operational_student

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
            "selected_courses": SEVEN_UNIT_COURSES,
            "payment_method": "cash",
            "tuition_total_rial": 52_000,
            "payment_amount_rial": 52_000,
            "invoice_amount": BACKUP_INVOICE_TOMAN,
        },
    )
    db_session.add(instance)
    await db_session.flush()

    patches = _patches()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        payable = await resolve_expected_payable_rial(db_session, instance)

    assert payable == SEVEN_UNIT_TOTAL


def test_cash_context_replaces_stale_interview_amount():
    ctx = apply_tuition_payment_context(
        {
            "tuition_total_rial": SEVEN_UNIT_TOTAL,
            "payment_amount_rial": 52_000,
            "payment_method": "cash",
        }
    )
    assert ctx["payable_amount_rial"] == SEVEN_UNIT_TOTAL
    assert ctx["payment_amount_rial"] == SEVEN_UNIT_TOTAL
    assert ctx["interview_payment_amount_rial"] == 52_000


@pytest.mark.asyncio
async def test_term1_catalog_list_is_not_billed_as_selection(db_session):
    patches = _patches()
    with ExitStack() as stack:
        for p in patches:
            stack.enter_context(p)
        fees = await resolve_registration_fees(
            db_session,
            "introductory_course_registration",
            {"available_courses": SEVEN_UNIT_COURSES},
            "payment",
        )
    assert fees["tuition_total_rial"] == BACKUP_INVOICE_TOMAN * 10
    assert fees["tuition_lines"] == []


@pytest.mark.asyncio
async def test_finance_panel_rate_updates_existing_offerings(db_session):
    from app.models.operational_models import InstituteCalendar, TermCourseOffering
    from app.services.financial_program_defaults_service import update_financial_program_defaults

    now = datetime.now(timezone.utc)
    cal = InstituteCalendar(
        id=uuid.uuid4(),
        term_code=f"term-{uuid.uuid4().hex[:6]}",
        is_active=True,
        term_start_date=now.date(),
        term_end_date=(now + timedelta(days=90)).date(),
        published_at=now,
        extra_data={"tuition": {"per_unit_cost_introductory": 1}},
    )
    db_session.add(cal)
    off = TermCourseOffering(
        id=uuid.uuid4(),
        term_code=cal.term_code,
        course_code="theory_psychoanalysis_1",
        course_name_fa="تئوری روانکاوی ۱",
        program_kind="introductory",
        term_number=1,
        units=2,
        per_unit_cost_rial=1,
        is_active=True,
        published_at=now,
    )
    db_session.add(off)
    await db_session.flush()

    await update_financial_program_defaults(
        db_session, {"per_unit_cost_introductory": PER_UNIT}
    )
    await db_session.refresh(off)
    assert off.per_unit_cost_rial == PER_UNIT
