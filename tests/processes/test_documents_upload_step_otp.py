"""دروازه OTP تأیید قوانین در مرحله آپلود مدارک ثبت‌نام آشنایی."""

from __future__ import annotations

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
from app.services.otp_service import request_otp


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
    seed = await seed_instance_at_state(
        db_session,
        "introductory_course_registration",
        "documents_upload",
        student_code=f"OTP-DOC-{Path(__file__).stem}"[:50],
    )
    await db_session.commit()
    assert seed.current_state == "documents_upload", (
        f"seed failed: mode={seed.mode} blocked={seed.blocked_at} got={seed.current_state}"
    )
    st = (
        await db_session.execute(select(Student).where(Student.id == seed.student_id))
    ).scalar_one()
    user = (await db_session.execute(select(User).where(User.id == st.user_id))).scalar_one()
    user.phone = "09123334455"
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
