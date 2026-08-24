"""دروازه OTP تأیید قوانین در مرحله آپلود مدارک ثبت‌نام آشنایی."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import create_access_token
from app.database import get_db
from app.flow_through.state_seeder import seed_instance_at_state
from app.main import app
from app.meta.seed import load_process
from app.meta.student_step_forms import CTX_STEP_OTP_VERIFIED_STATE
from app.models.operational_models import ProcessInstance, Student, User
from app.services.otp_service import STEP_OTP_EXPIRY_SECONDS, request_otp


PROCESSES_DIR = Path(__file__).resolve().parent.parent.parent / "metadata" / "processes"

DOC_VALUES = {
    "digital_commitment": True,
    "otp_code": "000000",
    "photo": {"file_name": "p.jpg", "url": "/uploads/p.jpg"},
    "id_card": {"file_name": "id.pdf", "url": "/uploads/id.pdf"},
    "national_card_front": {"file_name": "nf.pdf", "url": "/uploads/nf.pdf"},
    "national_card_back": {"file_name": "nb.pdf", "url": "/uploads/nb.pdf"},
    "bachelor_degree": {"file_name": "b.pdf", "url": "/uploads/b.pdf"},
    "latest_certificate": {"file_name": "l.pdf", "url": "/uploads/l.pdf"},
}


@pytest_asyncio.fixture
async def api_client(db_session: AsyncSession):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)


async def _seed_docs_upload(db_session: AsyncSession):
    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await db_session.commit()
    suffix = f"{uuid.uuid4().int % 10_000_000:07d}"
    seed = await seed_instance_at_state(
        db_session,
        "introductory_course_registration",
        "documents_upload",
        student_code=f"OTP-DOC-{suffix}"[:50],
    )
    await db_session.commit()
    assert seed.current_state == "documents_upload", (
        f"seed failed: mode={seed.mode} blocked={seed.blocked_at} got={seed.current_state}"
    )
    st = (
        await db_session.execute(select(Student).where(Student.id == seed.student_id))
    ).scalar_one()
    user = (await db_session.execute(select(User).where(User.id == st.user_id))).scalar_one()
    user.phone = f"0912{suffix}"
    await db_session.commit()
    token = create_access_token(
        {"sub": str(user.id), "username": user.username, "role": user.role}
    )
    return seed, user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_documents_upload_register_rejected_without_otp(
    db_session: AsyncSession, api_client: AsyncClient
):
    seed, _user, headers = await _seed_docs_upload(db_session)
    iid = str(seed.instance_id)
    reg = await api_client.post(
        f"/api/process/{iid}/student-step-forms/register",
        json={"form_values": DOC_VALUES},
        headers=headers,
    )
    assert reg.status_code == 400, reg.text
    detail = reg.json().get("detail")
    assert detail is not None
    # بدون فلگ سروری و بدون کد معتبر
    assert "کد" in str(detail) or "پیامک" in str(detail)


@pytest.mark.asyncio
async def test_documents_upload_register_after_step_otp_verify_advances(
    db_session: AsyncSession, api_client: AsyncClient
):
    seed, user, headers = await _seed_docs_upload(db_session)
    iid = str(seed.instance_id)

    req = await request_otp(db_session, user.phone)
    assert req.get("success") is True, req
    code = req.get("dev_code")
    if not code:
        from app.models.operational_models import OTPCode
        from sqlalchemy import desc

        row = (
            await db_session.execute(
                select(OTPCode)
                .where(OTPCode.phone == user.phone, OTPCode.is_used.is_(False))
                .order_by(desc(OTPCode.created_at))
            )
        ).scalars().first()
        assert row is not None
        code = row.code

    verify = await api_client.post(
        f"/api/process/{iid}/student-step-forms/step-otp/verify",
        json={"code": code},
        headers=headers,
    )
    assert verify.status_code == 200, verify.text
    assert verify.json().get("success") is True

    inst = await db_session.get(ProcessInstance, seed.instance_id)
    assert inst is not None
    await db_session.refresh(inst)
    assert (inst.context_data or {}).get(CTX_STEP_OTP_VERIFIED_STATE) == "documents_upload"

    payload = {**DOC_VALUES, "otp_code": code, "step_otp_verified": True}
    reg = await api_client.post(
        f"/api/process/{iid}/student-step-forms/register",
        json={"form_values": payload},
        headers=headers,
    )
    assert reg.status_code == 200, reg.text
    body = reg.json()
    assert body.get("success") is True
    assert body.get("auto_advanced_to_documents_review") is True

    await db_session.refresh(inst)
    assert inst.current_state_code == "documents_review"
    assert CTX_STEP_OTP_VERIFIED_STATE not in (inst.context_data or {})
    assert (inst.context_data or {}).get("step_otp_verified") is True


def _aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


@pytest.mark.asyncio
async def test_documents_upload_step_otp_request_is_valid_three_minutes(
    db_session: AsyncSession, api_client: AsyncClient
):
    seed, user, headers = await _seed_docs_upload(db_session)
    iid = str(seed.instance_id)

    req = await api_client.post(
        f"/api/process/{iid}/student-step-forms/step-otp/request",
        headers=headers,
    )
    assert req.status_code == 200, req.text
    body = req.json()
    assert body.get("success") is True
    assert body.get("expires_in") == STEP_OTP_EXPIRY_SECONDS == 180

    from app.models.operational_models import OTPCode
    from sqlalchemy import desc

    row = (
        await db_session.execute(
            select(OTPCode)
            .where(OTPCode.phone == user.phone, OTPCode.is_used.is_(False))
            .order_by(desc(OTPCode.created_at))
        )
    ).scalars().first()
    assert row is not None
    ttl = (_aware(row.expires_at) - _aware(row.created_at)).total_seconds()
    assert 179 <= ttl <= 181


@pytest.mark.asyncio
async def test_documents_upload_step_otp_rejected_after_three_minutes(
    db_session: AsyncSession, api_client: AsyncClient
):
    seed, user, headers = await _seed_docs_upload(db_session)
    iid = str(seed.instance_id)

    req = await request_otp(db_session, user.phone, expiry_seconds=STEP_OTP_EXPIRY_SECONDS)
    assert req.get("success") is True, req
    code = req.get("dev_code")
    assert code

    from app.models.operational_models import OTPCode
    from sqlalchemy import desc

    row = (
        await db_session.execute(
            select(OTPCode)
            .where(OTPCode.phone == user.phone, OTPCode.is_used.is_(False))
            .order_by(desc(OTPCode.created_at))
        )
    ).scalars().first()
    assert row is not None
    row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    await db_session.commit()

    verify = await api_client.post(
        f"/api/process/{iid}/student-step-forms/step-otp/verify",
        json={"code": code},
        headers=headers,
    )
    assert verify.status_code == 400, verify.text
    detail = str(verify.json().get("detail") or "")
    assert "منقضی" in detail or "نامعتبر" in detail


@pytest.mark.asyncio
async def test_documents_upload_step_otp_still_valid_before_three_minutes(
    db_session: AsyncSession, api_client: AsyncClient
):
    seed, user, headers = await _seed_docs_upload(db_session)
    iid = str(seed.instance_id)

    req = await request_otp(db_session, user.phone, expiry_seconds=STEP_OTP_EXPIRY_SECONDS)
    assert req.get("success") is True, req
    code = req.get("dev_code")
    assert code

    from app.models.operational_models import OTPCode
    from sqlalchemy import desc

    row = (
        await db_session.execute(
            select(OTPCode)
            .where(OTPCode.phone == user.phone, OTPCode.is_used.is_(False))
            .order_by(desc(OTPCode.created_at))
        )
    ).scalars().first()
    assert row is not None
    row.expires_at = datetime.now(timezone.utc) + timedelta(seconds=5)
    await db_session.commit()

    verify = await api_client.post(
        f"/api/process/{iid}/student-step-forms/step-otp/verify",
        json={"code": code},
        headers=headers,
    )
    assert verify.status_code == 200, verify.text
    assert verify.json().get("success") is True


def test_context_has_step_otp_verified_keeps_durable_flag_across_states():
    from app.meta.student_step_forms import context_has_step_otp_verified

    assert context_has_step_otp_verified({"step_otp_verified": True}, "documents_incomplete") is True
    assert context_has_step_otp_verified({}, "documents_upload") is False
    assert context_has_step_otp_verified(
        {CTX_STEP_OTP_VERIFIED_STATE: "documents_upload"},
        "documents_incomplete",
    ) is False


def test_validate_documents_resubmit_skips_otp_when_already_verified():
    from app.meta.process_forms import get_process_forms
    from app.meta.student_step_forms import CTX_DOCUMENTS_RESUBMIT_FIELDS, validate_student_step_forms

    forms = get_process_forms("introductory_course_registration", "documents_incomplete")
    ok, missing = validate_student_step_forms(
        forms,
        {
            "digital_commitment": True,
            "photo": {"file_name": "p.jpg", "url": "/uploads/p.jpg"},
        },
        {
            "step_otp_verified": True,
            CTX_DOCUMENTS_RESUBMIT_FIELDS: ["photo"],
        },
    )
    assert ok is True, missing


async def _seed_docs_incomplete(db_session: AsyncSession, *, otp_verified: bool = True):
    from sqlalchemy.orm.attributes import flag_modified

    from app.meta.student_step_forms import CTX_DOCUMENTS_RESUBMIT_FIELDS

    await load_process(db_session, PROCESSES_DIR / "introductory_course_registration.json")
    await db_session.commit()
    suffix = f"{uuid.uuid4().int % 10_000_000:07d}"
    seed = await seed_instance_at_state(
        db_session,
        "introductory_course_registration",
        "documents_incomplete",
        student_code=f"OTP-INC-{suffix}"[:50],
        extra_ctx={
            "step_otp_verified": otp_verified,
            CTX_DOCUMENTS_RESUBMIT_FIELDS: ["photo"],
            "digital_commitment": True,
        },
    )
    await db_session.commit()
    assert seed.current_state == "documents_incomplete", (
        f"seed failed: mode={seed.mode} blocked={seed.blocked_at} got={seed.current_state}"
    )
    inst = await db_session.get(ProcessInstance, seed.instance_id)
    assert inst is not None
    ctx = dict(inst.context_data or {})
    if otp_verified:
        ctx["step_otp_verified"] = True
    else:
        ctx.pop("step_otp_verified", None)
        ctx.pop(CTX_STEP_OTP_VERIFIED_STATE, None)
    ctx[CTX_DOCUMENTS_RESUBMIT_FIELDS] = ["photo"]
    ctx["digital_commitment"] = True
    inst.context_data = ctx
    flag_modified(inst, "context_data")
    st = (
        await db_session.execute(select(Student).where(Student.id == seed.student_id))
    ).scalar_one()
    user = (await db_session.execute(select(User).where(User.id == st.user_id))).scalar_one()
    user.phone = f"0913{suffix}"
    await db_session.commit()
    token = create_access_token(
        {"sub": str(user.id), "username": user.username, "role": user.role}
    )
    return seed, user, {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_documents_incomplete_skips_otp_when_already_verified(
    db_session: AsyncSession, api_client: AsyncClient
):
    from app.models.operational_models import OTPCode

    seed, user, headers = await _seed_docs_incomplete(db_session, otp_verified=True)
    iid = str(seed.instance_id)

    n_before = len(
        list(
            (
                await db_session.execute(select(OTPCode).where(OTPCode.phone == user.phone))
            ).scalars().all()
        )
    )
    req = await api_client.post(
        f"/api/process/{iid}/student-step-forms/step-otp/request",
        headers=headers,
    )
    assert req.status_code == 200, req.text
    body = req.json()
    assert body.get("success") is True
    assert body.get("already_verified") is True
    n_after = len(
        list(
            (
                await db_session.execute(select(OTPCode).where(OTPCode.phone == user.phone))
            ).scalars().all()
        )
    )
    assert n_after == n_before

    reg = await api_client.post(
        f"/api/process/{iid}/student-step-forms/register",
        json={
            "form_values": {
                "digital_commitment": True,
                "photo": {"file_name": "fixed.jpg", "url": "/uploads/fixed.jpg"},
            }
        },
        headers=headers,
    )
    assert reg.status_code == 200, reg.text
    assert reg.json().get("success") is True


@pytest.mark.asyncio
async def test_documents_incomplete_still_requires_otp_if_never_verified(
    db_session: AsyncSession, api_client: AsyncClient
):
    seed, _user, headers = await _seed_docs_incomplete(db_session, otp_verified=False)
    iid = str(seed.instance_id)
    reg = await api_client.post(
        f"/api/process/{iid}/student-step-forms/register",
        json={
            "form_values": {
                "digital_commitment": True,
                "photo": {"file_name": "fixed.jpg", "url": "/uploads/fixed.jpg"},
            }
        },
        headers=headers,
    )
    assert reg.status_code == 400, reg.text
    detail = str(reg.json().get("detail") or "")
    assert "کد" in detail or "پیامک" in detail or "otp" in detail.lower() or "validation" in detail.lower()
