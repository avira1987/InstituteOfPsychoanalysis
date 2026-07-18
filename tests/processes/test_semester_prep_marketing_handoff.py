"""تست خروجی کمپین بازاریابی و اعتبارسنجی ثبت فرم قبل از transition."""

from pathlib import Path
from datetime import datetime, timezone

import pytest
import pytest_asyncio
from fastapi import HTTPException
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.api.process.routes import _validate_semester_prep_step_form_submitted
from app.core.engine import StateMachineEngine
from app.main import app
from app.database import get_db
from app.api.auth import get_current_user
from app.meta.seed import load_process
from app.meta.student_step_forms import apply_register_to_context
from app.models.operational_models import ProcessInstance
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_service import FALL_PREP, WINTER_PREP, get_or_start_prep_instance

CALENDAR_VALUES = {
    "fall_start_date": "2026-09-23",
    "fall_end_date": "2026-12-21",
    "winter_start_date": "2026-12-22",
    "winter_end_date": "2027-03-20",
    "registration_payment_window_start": "2026-08-01",
    "registration_payment_window_end": "2026-09-01",
    "intern_interview_deadline": "2026-08-15",
    "teaching_assistant_interview_deadline": "2026-08-20",
    "nowruz_holiday_start": "2027-03-21",
    "nowruz_holiday_end": "2027-04-02",
}

TUITION_VALUES = {
    "per_unit_cost_introductory": 1_000_000,
    "per_unit_cost_comprehensive": 2_000_000,
    "interview_fee_introductory": 500_000,
    "interview_fee_comprehensive": 600_000,
}

COURSE_ROW = {
    "course_name": "روانکاوی ۱",
    "track": "",
    "proposed_day": "دوشنبه",
    "proposed_time": "18:00",
    "instructor": "",
    "teaching_assistant": "",
}


@pytest_asyncio.fixture
async def process_api_client(db_session: AsyncSession, sample_user):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return sample_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture
async def fall_prep_instance(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await db_session.commit()
    anchor = await ensure_institute_operational_student(db_session)
    inst, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    await db_session.commit()
    return inst, anchor


def test_validate_semester_prep_requires_submitted_form():
    inst = ProcessInstance(
        process_code=FALL_PREP,
        current_state_code="calendar_entry",
        context_data={},
    )
    with pytest.raises(HTTPException) as exc:
        _validate_semester_prep_step_form_submitted(inst, "calendar_submitted")
    assert "ثبت فرم" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_api_trigger_blocked_without_form_submit(process_api_client, fall_prep_instance):
    instance, _ = fall_prep_instance
    r = await process_api_client.post(
        f"/api/process/{instance.id}/trigger",
        json={"trigger_event": "calendar_submitted"},
    )
    assert r.status_code == 400
    assert "ثبت فرم" in (r.json().get("detail") or "")


@pytest.mark.asyncio
async def test_api_trigger_after_form_register_advances(
    process_api_client, fall_prep_instance, db_session
):
    instance, _ = fall_prep_instance
    reg = await process_api_client.post(
        f"/api/process/{instance.id}/operator-step-forms/register",
        json={"state_code": "calendar_entry", "form_values": CALENDAR_VALUES},
    )
    assert reg.status_code == 200, reg.text

    r = await process_api_client.post(
        f"/api/process/{instance.id}/trigger",
        json={"trigger_event": "calendar_submitted"},
    )
    assert r.status_code == 200
    assert r.json().get("to_state") == "tuition_entry"


@pytest.mark.asyncio
async def test_fall_prep_reaches_marketing_with_context_via_form_register(
    process_api_client, fall_prep_instance, db_session, sample_user
):
    instance, _ = fall_prep_instance
    engine = StateMachineEngine(db_session)

    steps = [
        ("calendar_entry", CALENDAR_VALUES, "calendar_submitted", "tuition_entry"),
        ("tuition_entry", TUITION_VALUES, "tuition_submitted", "license_check"),
        ("license_check", {"license_status": "بدون تغییر"}, "license_reviewed", "course_list_creation"),
        (
            "course_list_creation",
            {"courses_fall": [COURSE_ROW], "courses_winter": [COURSE_ROW]},
            "course_list_submitted",
            "course_finalization",
        ),
    ]

    for state, values, trigger, expected_next in steps:
        reg = await process_api_client.post(
            f"/api/process/{instance.id}/operator-step-forms/register",
            json={"state_code": state, "form_values": values},
        )
        assert reg.status_code == 200, f"register {state}: {reg.text}"
        tr = await process_api_client.post(
            f"/api/process/{instance.id}/trigger",
            json={"trigger_event": trigger},
        )
        assert tr.status_code == 200, f"trigger {trigger}: {tr.text}"
        assert tr.json().get("to_state") == expected_next

    instance = await engine.get_process_instance(instance.id)
    ctx = dict(instance.context_data or {})
    finalized_fall = [
        {
            **COURSE_ROW,
            "day": COURSE_ROW["proposed_day"],
            "time": COURSE_ROW["proposed_time"],
            "classroom_location": "کلاس ۱",
            "instructor_coordinated": True,
        }
    ]
    finalized_winter = [
        {
            **COURSE_ROW,
            "day": COURSE_ROW["proposed_day"],
            "time": COURSE_ROW["proposed_time"],
            "classroom_location": "کلاس ۲",
            "instructor_coordinated": True,
        }
    ]
    ctx = apply_register_to_context(
        ctx,
        "course_finalization",
        {
            "courses_finalized_fall": finalized_fall,
            "courses_finalized_winter": finalized_winter,
        },
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db_session.commit()

    tr = await process_api_client.post(
        f"/api/process/{instance.id}/trigger",
        json={"trigger_event": "courses_finalized"},
    )
    assert tr.status_code == 200
    assert tr.json().get("to_state") == "marketing_campaign"

    instance = await engine.get_process_instance(instance.id)
    mctx = dict(instance.context_data or {})
    assert mctx.get("fall_start_date") == CALENDAR_VALUES["fall_start_date"]
    assert mctx.get("per_unit_cost_introductory") == TUITION_VALUES["per_unit_cost_introductory"]
    assert len(mctx.get("courses_finalized_fall") or []) >= 1

    from app.services.semester_prep_marketing_pdf import (
        build_marketing_campaign_pdf_rows,
        has_marketing_handoff_data,
    )

    assert has_marketing_handoff_data(FALL_PREP, mctx) is True
    rows = build_marketing_campaign_pdf_rows(FALL_PREP, mctx)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "فعالیت ۱" in flat
    assert "فعالیت ۵" in flat
    assert "روانکاوی ۱" in flat


@pytest_asyncio.fixture
async def winter_prep_instance(db_session: AsyncSession, sample_user):
    processes_dir = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"
    await load_process(db_session, processes_dir / "fall_semester_preparation.json")
    await load_process(db_session, processes_dir / "winter_semester_preparation.json")
    await db_session.commit()

    anchor = await ensure_institute_operational_student(db_session)
    engine = StateMachineEngine(db_session)
    fall, _ = await get_or_start_prep_instance(
        db_session, FALL_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    fall.is_completed = True
    fall.current_state_code = "published"
    fall.completed_at = datetime.now(timezone.utc)
    fall.context_data = {
        **CALENDAR_VALUES,
        **TUITION_VALUES,
        "courses_winter": [COURSE_ROW],
        "courses_finalized_winter": [
            {
                **COURSE_ROW,
                "day": COURSE_ROW["proposed_day"],
                "time": COURSE_ROW["proposed_time"],
                "classroom_location": "کلاس ۲",
                "instructor_coordinated": True,
            }
        ],
    }
    flag_modified(fall, "context_data")
    await db_session.commit()

    inst, _ = await get_or_start_prep_instance(
        db_session, WINTER_PREP, actor_id=sample_user.id, actor_role="admin"
    )
    await db_session.commit()
    return inst, anchor, engine


@pytest.mark.asyncio
async def test_winter_prep_reaches_marketing_with_context_via_form_register(
    process_api_client, winter_prep_instance, db_session, sample_user
):
    instance, _, engine = winter_prep_instance

    steps = [
        ("license_check", {"license_status": "بدون تغییر"}, "license_reviewed", "course_list_review"),
        (
            "course_list_review",
            {"courses": [COURSE_ROW]},
            "course_list_reviewed",
            "course_finalization",
        ),
    ]

    for state, values, trigger, expected_next in steps:
        reg = await process_api_client.post(
            f"/api/process/{instance.id}/operator-step-forms/register",
            json={"state_code": state, "form_values": values},
        )
        assert reg.status_code == 200, f"register {state}: {reg.text}"
        tr = await process_api_client.post(
            f"/api/process/{instance.id}/trigger",
            json={"trigger_event": trigger},
        )
        assert tr.status_code == 200, f"trigger {trigger}: {tr.text}"
        assert tr.json().get("to_state") == expected_next

    instance = await engine.get_process_instance(instance.id)
    ctx = dict(instance.context_data or {})
    finalized = [
        {
            **COURSE_ROW,
            "day": COURSE_ROW["proposed_day"],
            "time": COURSE_ROW["proposed_time"],
            "classroom_location": "کلاس زمستان",
            "instructor_coordinated": True,
        }
    ]
    ctx = apply_register_to_context(
        ctx,
        "course_finalization",
        {"courses_finalized": finalized},
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db_session.commit()

    tr = await process_api_client.post(
        f"/api/process/{instance.id}/trigger",
        json={"trigger_event": "courses_finalized"},
    )
    assert tr.status_code == 200
    assert tr.json().get("to_state") == "marketing_campaign"

    instance = await engine.get_process_instance(instance.id)
    mctx = dict(instance.context_data or {})
    assert len(mctx.get("courses_finalized") or []) >= 1

    from app.services.semester_prep_marketing_pdf import (
        build_marketing_campaign_pdf_rows,
        has_marketing_handoff_data,
    )

    assert has_marketing_handoff_data(WINTER_PREP, mctx) is True
    rows = build_marketing_campaign_pdf_rows(WINTER_PREP, mctx)
    flat = " ".join(str(c) for r in rows for c in r)
    assert "فعالیت ۲" in flat
    assert "فعالیت ۳" in flat
    assert "روانکاوی ۱" in flat


async def _advance_winter_to_marketing(process_api_client, instance, engine, db_session):
    """Advance winter prep instance to marketing_campaign state."""
    steps = [
        ("license_check", {"license_status": "بدون تغییر"}, "license_reviewed", "course_list_review"),
        (
            "course_list_review",
            {"courses": [COURSE_ROW]},
            "course_list_reviewed",
            "course_finalization",
        ),
    ]

    for state, values, trigger, expected_next in steps:
        reg = await process_api_client.post(
            f"/api/process/{instance.id}/operator-step-forms/register",
            json={"state_code": state, "form_values": values},
        )
        assert reg.status_code == 200, f"register {state}: {reg.text}"
        tr = await process_api_client.post(
            f"/api/process/{instance.id}/trigger",
            json={"trigger_event": trigger},
        )
        assert tr.status_code == 200, f"trigger {trigger}: {tr.text}"
        assert tr.json().get("to_state") == expected_next

    instance = await engine.get_process_instance(instance.id)
    ctx = dict(instance.context_data or {})
    finalized = [
        {
            **COURSE_ROW,
            "day": COURSE_ROW["proposed_day"],
            "time": COURSE_ROW["proposed_time"],
            "classroom_location": "کلاس زمستان",
            "instructor_coordinated": True,
        }
    ]
    ctx = apply_register_to_context(
        ctx,
        "course_finalization",
        {"courses_finalized": finalized},
    )
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db_session.commit()

    tr = await process_api_client.post(
        f"/api/process/{instance.id}/trigger",
        json={"trigger_event": "courses_finalized"},
    )
    assert tr.status_code == 200
    assert tr.json().get("to_state") == "marketing_campaign"
    return await engine.get_process_instance(instance.id)


@pytest.mark.asyncio
async def test_marketing_pdf_download_admin_success(
    process_api_client, winter_prep_instance, db_session
):
    instance, _, engine = winter_prep_instance
    instance = await _advance_winter_to_marketing(process_api_client, instance, engine, db_session)

    r = await process_api_client.get(
        f"/api/process/{instance.id}/marketing-campaign-pack.pdf",
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
    cd = r.headers.get("content-disposition") or ""
    assert "marketing_campaign_winter" in cd


@pytest.mark.asyncio
async def test_marketing_pdf_download_wrong_state_returns_400(
    process_api_client, winter_prep_instance
):
    instance, _, _ = winter_prep_instance
    assert instance.current_state_code != "marketing_campaign"

    r = await process_api_client.get(
        f"/api/process/{instance.id}/marketing-campaign-pack.pdf",
    )
    assert r.status_code == 400
    assert "کمپین بازاریابی" in (r.json().get("detail") or "")


@pytest_asyncio.fixture
async def student_process_api_client(db_session: AsyncSession, sample_student_user):
    async def override_get_db():
        yield db_session

    async def override_get_current_user():
        return sample_student_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_marketing_pdf_download_student_forbidden(
    student_process_api_client, winter_prep_instance, db_session
):
    instance, _, _ = winter_prep_instance
    instance.current_state_code = "marketing_campaign"
    ctx = dict(instance.context_data or {})
    ctx["courses_finalized"] = [
        {
            **COURSE_ROW,
            "day": COURSE_ROW["proposed_day"],
            "time": COURSE_ROW["proposed_time"],
            "classroom_location": "کلاس زمستان",
            "instructor_coordinated": True,
        }
    ]
    instance.context_data = ctx
    flag_modified(instance, "context_data")
    await db_session.commit()

    r = await student_process_api_client.get(
        f"/api/process/{instance.id}/marketing-campaign-pack.pdf",
    )
    assert r.status_code == 403
