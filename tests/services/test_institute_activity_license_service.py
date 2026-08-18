"""شماره پروانه فعالیت انستیتو — ذخیره روی INST-OPS و نمایش در فرم پذیرش."""

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.database import get_db
from app.main import app
from app.models.operational_models import ProcessInstance
from app.services.action_handler import ActionHandler
from app.services.institute_activity_license_service import (
    LICENSE_NUMBER_KEY,
    SOURCE_MANUAL,
    SOURCE_PREP,
    activity_license_public_payload,
    get_activity_license_number,
    get_activity_license_record,
    set_activity_license_number,
    sync_activity_license_from_prep_context,
)
from app.services.institute_operational_anchor import ensure_institute_operational_student
from app.services.semester_prep_service import FALL_PREP, apply_pre_filled_fields


@pytest.mark.asyncio
async def test_get_empty_then_set_on_inst_ops(db_session: AsyncSession):
    assert await get_activity_license_number(db_session) is None
    rec = await set_activity_license_number(db_session, "  12345  ", source=SOURCE_MANUAL)
    assert rec["activity_license_number"] == "12345"
    assert rec["source"] == SOURCE_MANUAL
    assert rec["updated_at"]
    assert rec["student_code"] == "INST-OPS"

    anchor = await ensure_institute_operational_student(db_session)
    extra = anchor.extra_data or {}
    assert extra.get("institute_operational_anchor") is True
    assert extra.get(LICENSE_NUMBER_KEY) == "12345"
    assert await get_activity_license_number(db_session) == "12345"


@pytest.mark.asyncio
async def test_set_empty_string_does_not_clear(db_session: AsyncSession):
    await set_activity_license_number(db_session, "KEEP-1", source=SOURCE_MANUAL)
    rec = await set_activity_license_number(db_session, "   ", source=SOURCE_PREP)
    assert rec["activity_license_number"] == "KEEP-1"
    assert rec["source"] == SOURCE_MANUAL


@pytest.mark.asyncio
async def test_sync_from_prep_changes_number_only_when_status_changed(db_session: AsyncSession):
    await set_activity_license_number(db_session, "OLD-1", source=SOURCE_MANUAL)

    unchanged = await sync_activity_license_from_prep_context(
        db_session,
        {"license_status": "بدون تغییر", "new_license_number": "NEW-9"},
    )
    assert unchanged["activity_license_number"] == "OLD-1"

    empty_changed = await sync_activity_license_from_prep_context(
        db_session,
        {"license_status": "تغییر کرده", "new_license_number": "  "},
    )
    assert empty_changed["activity_license_number"] == "OLD-1"

    changed = await sync_activity_license_from_prep_context(
        db_session,
        {"license_status": "تغییر کرده", "new_license_number": "NEW-9"},
    )
    assert changed["activity_license_number"] == "NEW-9"
    assert changed["source"] == SOURCE_PREP


@pytest.mark.asyncio
async def test_action_handler_syncs_license_from_instance_context(
    db_session: AsyncSession, sample_student
):
    await set_activity_license_number(db_session, "A-1", source=SOURCE_MANUAL)
    instance = ProcessInstance(
        id=uuid.uuid4(),
        process_code=FALL_PREP,
        student_id=sample_student.id,
        current_state_code="license_check",
        context_data={"license_status": "تغییر کرده", "new_license_number": "B-2"},
    )
    db_session.add(instance)
    await db_session.flush()

    handler = ActionHandler(db_session)
    results = await handler.handle_actions(
        [{"type": "sync_institute_license_from_prep"}],
        instance,
        {},
    )
    assert results[0]["success"] is True
    assert await get_activity_license_number(db_session) == "B-2"


@pytest.mark.asyncio
async def test_action_handler_unchanged_keeps_stored_number(
    db_session: AsyncSession, sample_student
):
    await set_activity_license_number(db_session, "KEEP-2", source=SOURCE_MANUAL)
    instance = ProcessInstance(
        id=uuid.uuid4(),
        process_code=FALL_PREP,
        student_id=sample_student.id,
        current_state_code="license_check",
        context_data={"license_status": "بدون تغییر"},
    )
    db_session.add(instance)
    await db_session.flush()

    handler = ActionHandler(db_session)
    results = await handler.handle_actions(
        [{"type": "sync_institute_license_from_prep"}],
        instance,
        {},
    )
    assert results[0]["success"] is True
    assert await get_activity_license_number(db_session) == "KEEP-2"


@pytest.mark.asyncio
async def test_prefill_injects_current_license_number(db_session: AsyncSession):
    await set_activity_license_number(db_session, "PREFILL-7", source=SOURCE_MANUAL)
    merged = await apply_pre_filled_fields(
        db_session, FALL_PREP, "license_check", {"license_status": "بدون تغییر"}
    )
    assert merged["current_license_number"] == "PREFILL-7"


def test_public_payload_omits_internal_fields():
    payload = activity_license_public_payload("X-1")
    assert payload == {"activity_license_number": "X-1"}
    assert "student_code" not in payload
    assert "source" not in payload
    empty = activity_license_public_payload(None)
    assert empty == {"activity_license_number": None}


@pytest_asyncio.fixture
async def license_api_client(db_session: AsyncSession, sample_user):
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


@pytest.mark.asyncio
async def test_admin_patch_license_without_prep_instance(
    db_session: AsyncSession, license_api_client
):
    res = await license_api_client.patch(
        "/api/admin/semester-prep/activity-license",
        json={"activity_license_number": "MAN-88"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["activity_license_number"] == "MAN-88"
    assert body["source"] == SOURCE_MANUAL
    assert "student_code" in body

    got = await license_api_client.get("/api/admin/semester-prep/activity-license")
    assert got.status_code == 200
    assert got.json()["activity_license_number"] == "MAN-88"
    rec = await get_activity_license_record(db_session)
    assert rec["activity_license_number"] == "MAN-88"


@pytest.mark.asyncio
async def test_public_institute_info_returns_number_only(
    db_session: AsyncSession, license_api_client
):
    empty = await license_api_client.get("/api/public/institute-info")
    assert empty.status_code == 200
    assert empty.json() == {"activity_license_number": None}

    await set_activity_license_number(db_session, "PUB-42", source=SOURCE_PREP)
    await db_session.commit()

    res = await license_api_client.get("/api/public/institute-info")
    assert res.status_code == 200
    assert res.json() == {"activity_license_number": "PUB-42"}
    assert "student_code" not in res.json()
    assert "source" not in res.json()
