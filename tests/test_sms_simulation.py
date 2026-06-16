"""پیامک شبیه‌سازی‌شده (SMS_PROVIDER=log) و outbox پنل."""

import random
import uuid
import pytest
from sqlalchemy import select, func

from app.config import get_settings
from app.models.operational_models import SmsSimulationOutbox
from app.services import sms_gateway as sg
from app.services import otp_service as otps
from app.services import sms_simulation_service as sim


def _reload_sms_settings() -> None:
    get_settings.cache_clear()
    sg.settings = get_settings()


@pytest.fixture
def sms_log_with_ui(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "log")
    monkeypatch.setenv("SMS_SIMULATION_UI", "true")
    _reload_sms_settings()
    yield
    get_settings.cache_clear()
    sg.settings = get_settings()


@pytest.fixture
def sms_real_provider(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "mellipayamak")
    monkeypatch.setenv("SMS_SIMULATION_UI", "true")
    _reload_sms_settings()
    yield
    monkeypatch.setenv("SMS_PROVIDER", "log")
    get_settings.cache_clear()
    sg.settings = get_settings()


def _random_mobile() -> str:
    """۱۱ رقم استاندارد: ۰۹ به‌اضافهٔ ۹ رقم."""
    return "09" + "".join(random.choice("0123456789") for _ in range(9))


@pytest.mark.asyncio
async def test_send_sms_log_writes_outbox(db_session, sms_log_with_ui):
    phone = _random_mobile()
    await sg.send_sms(phone, "سلام تست بدون قالب")

    cnt = (
        await db_session.execute(select(func.count()).select_from(SmsSimulationOutbox).where(SmsSimulationOutbox.phone == phone))
    ).scalar_one()
    assert cnt == 1
    row = (
        (
            await db_session.execute(select(SmsSimulationOutbox).where(SmsSimulationOutbox.phone == phone).limit(1))
        )
        .scalars()
        .first()
    )
    assert row is not None
    assert row.message == "سلام تست بدون قالب"
    assert row.kind == "free_text"


@pytest.mark.asyncio
async def test_list_pending_own_phone_only(db_session, sms_log_with_ui, sample_student_user):
    phone_me = "09121112233"
    phone_other = "09123334444"
    sample_student_user.phone = phone_me
    await db_session.commit()

    sid = uuid.uuid4()
    db_session.add_all(
        [
            SmsSimulationOutbox(
                id=sid,
                phone=phone_me,
                message="به من",
                kind="notification",
                template_key="leave_approved",
            ),
            SmsSimulationOutbox(
                id=uuid.uuid4(),
                phone=phone_other,
                message="به دیگری",
                kind="free_text",
                template_key=None,
            ),
        ]
    )
    await db_session.commit()

    pending = await sim.list_pending_for_user(db_session, sample_student_user, limit=50)
    assert len(pending) == 1
    assert pending[0]["id"] == str(sid)
    assert pending[0]["message"] == "به من"


@pytest.mark.asyncio
async def test_dismiss_hidden_from_list(db_session, sms_log_with_ui, sample_student_user):
    phone_me = "09125556677"
    sample_student_user.phone = phone_me
    await db_session.commit()

    row = SmsSimulationOutbox(id=uuid.uuid4(), phone=phone_me, message="x", kind="otp")
    db_session.add(row)
    await db_session.commit()

    pending = await sim.list_pending_for_user(db_session, sample_student_user, limit=50)
    assert len(pending) == 1

    ok = await sim.dismiss(db_session, sample_student_user, row.id)
    assert ok is True

    pending2 = await sim.list_pending_for_user(db_session, sample_student_user, limit=50)
    assert len(pending2) == 0


@pytest.mark.asyncio
async def test_list_pending_uses_username_when_phone_empty(db_session, sms_log_with_ui, sample_student_user):
    """دانشجو با username=موبایل و phone خالی — همان inbox باید کار کند."""
    phone_me = "09128887766"
    sample_student_user.phone = None
    sample_student_user.username = phone_me
    await db_session.commit()

    sid = uuid.uuid4()
    db_session.add(
        SmsSimulationOutbox(
            id=sid,
            phone=phone_me,
            message="به نام کاربری موبایلی",
            kind="free_text",
            template_key=None,
        )
    )
    await db_session.commit()

    pending = await sim.list_pending_for_user(db_session, sample_student_user, limit=50)
    assert len(pending) == 1
    assert pending[0]["id"] == str(sid)


@pytest.mark.asyncio
async def test_mellipayamak_skip_outbox(monkeypatch, db_session, sms_real_provider):
    async def fake_mellipayamak(_phone: str, _msg: str) -> dict:
        return {"success": True, "provider": "mellipayamak"}

    monkeypatch.setattr(sg, "_send_mellipayamak", fake_mellipayamak)

    p = _random_mobile()
    await sg.send_sms(p, "پیام واقعی نیست")

    cnt = (
        await db_session.execute(select(func.count()).select_from(SmsSimulationOutbox).where(SmsSimulationOutbox.phone == p))
    ).scalar_one()
    assert cnt == 0


@pytest.mark.asyncio
async def test_send_sms_disabled_ui_writes_no_rows(monkeypatch, db_session):
    monkeypatch.setenv("SMS_PROVIDER", "log")
    monkeypatch.setenv("SMS_SIMULATION_UI", "false")
    _reload_sms_settings()

    p = _random_mobile()
    res = await sg.send_sms(p, " خاموش ")
    assert res.get("success") is True
    assert res.get("simulated_sms_id") is None

    cnt = (
        await db_session.execute(select(func.count()).select_from(SmsSimulationOutbox).where(SmsSimulationOutbox.phone == p))
    ).scalar_one()
    assert cnt == 0

    monkeypatch.setenv("SMS_SIMULATION_UI", "true")
    _reload_sms_settings()


@pytest.mark.asyncio
async def test_request_otp_returns_simulated_sms(db_session, sms_log_with_ui):
    phone = _random_mobile()
    res = await otps.request_otp(db_session, phone)
    assert res.get("success") is True
    simsms = res.get("simulated_sms")
    assert simsms is not None
    assert simsms["phone"] == phone
    assert "کد ورود" in simsms["message"]


@pytest.mark.asyncio
async def test_admin_global_feed_lists_all_phones(db_session, sms_log_with_ui, sample_user):
    assert (sample_user.role or "").strip() == "admin"
    p1 = "09158881111"
    p2 = "09159992222"
    db_session.add_all(
        [
            SmsSimulationOutbox(
                id=uuid.uuid4(), phone=p1, message="به یک", kind="free_text", template_key=None
            ),
            SmsSimulationOutbox(
                id=uuid.uuid4(), phone=p2, message="به دو", kind="notification", template_key="x",
            ),
        ]
    )
    await db_session.commit()

    pending = await sim.list_pending_for_user(db_session, sample_user, limit=50)
    phones = {x["phone"] for x in pending}
    assert phones == {p1, p2}


@pytest.mark.asyncio
async def test_student_own_phone_only_under_global_popup_setting(db_session, sms_log_with_ui, sample_student_user):
    mine = "09156667777"
    other = "09157778888"
    sample_student_user.phone = mine
    await db_session.commit()
    sid_m = uuid.uuid4()
    sid_o = uuid.uuid4()
    db_session.add_all(
        [
            SmsSimulationOutbox(id=sid_m, phone=mine, message="baray man", kind="otp"),
            SmsSimulationOutbox(id=sid_o, phone=other, message="baray digari", kind="free_text"),
        ]
    )
    await db_session.commit()

    pending = await sim.list_pending_for_user(db_session, sample_student_user, limit=50)
    assert len(pending) == 1
    assert pending[0]["phone"] == mine


@pytest.mark.asyncio
async def test_popup_show_all_false_admin_gets_own_line_only(monkeypatch, db_session, sms_log_with_ui, sample_user):
    monkeypatch.setenv("SMS_SIMULATION_POPUP_SHOW_ALL", "false")
    _reload_sms_settings()

    adm_phone = "09154443322"
    other = "09153332211"
    sample_user.phone = adm_phone
    await db_session.commit()
    db_session.add_all(
        [
            SmsSimulationOutbox(id=uuid.uuid4(), phone=adm_phone, message="به مدیریت", kind="free_text"),
            SmsSimulationOutbox(id=uuid.uuid4(), phone=other, message="به دیگر", kind="free_text"),
        ]
    )
    await db_session.commit()

    pending = await sim.list_pending_for_user(db_session, sample_user, limit=50)
    assert len(pending) == 1
    assert pending[0]["phone"] == adm_phone

    monkeypatch.setenv("SMS_SIMULATION_POPUP_SHOW_ALL", "true")
    _reload_sms_settings()


def test_resolve_sms_message_body_process_fallback():
    from app.services.notification_service import resolve_sms_message_body
    from app.services.sms_process_template_texts import process_sms_template_texts

    proc = process_sms_template_texts()
    if not proc:
        pytest.skip("no process metadata sms templates")
    key, text = next(iter(proc.items()))
    body = resolve_sms_message_body(key, {})
    assert text[:40] in body or body == text


@pytest.mark.asyncio
async def test_mirror_real_send_after_mellipayamak(monkeypatch, db_session, sms_real_provider):
    monkeypatch.setenv("SMS_SIMULATION_MIRROR_REAL_SEND", "true")
    _reload_sms_settings()

    phone = _random_mobile()

    async def fake_send(phone_arg, message):
        return {"success": True, "provider": "mellipayamak_rest", "response": {}}

    monkeypatch.setattr(sg, "_send_mellipayamak", fake_send)
    res = await sg.send_sms(phone, "متن آزمایشی mirror", template_key=None)
    assert res.get("success")
    assert res.get("simulated_sms", {}).get("message") == "متن آزمایشی mirror"

    row = (
        await db_session.execute(
            select(SmsSimulationOutbox).where(SmsSimulationOutbox.phone == phone).limit(1)
        )
    ).scalars().first()
    assert row is not None
    assert row.message == "متن آزمایشی mirror"


    monkeypatch.setenv("SMS_SIMULATION_POPUP_SHOW_ALL", "true")
    _reload_sms_settings()


@pytest.mark.asyncio
async def test_list_student_sms_history_excludes_otp_and_welcome(
    db_session, sms_log_with_ui, sample_student_user,
):
    mine = "09121112233"
    other = "09124445566"
    sample_student_user.phone = mine
    await db_session.commit()
    db_session.add_all(
        [
            SmsSimulationOutbox(id=uuid.uuid4(), phone=mine, message="کد ورود 123456", kind="otp"),
            SmsSimulationOutbox(
                id=uuid.uuid4(),
                phone=mine,
                message="رمز: 999999",
                kind="notification",
                template_key="student_portal_welcome_credentials",
            ),
            SmsSimulationOutbox(
                id=uuid.uuid4(),
                phone=mine,
                message="مصاحبه شما فردا برگزار می‌شود",
                kind="notification",
                template_key="interview_confirmation_applicant",
            ),
            SmsSimulationOutbox(
                id=uuid.uuid4(), phone=other, message="به دیگری", kind="notification"
            ),
        ]
    )
    await db_session.commit()

    history = await sim.list_student_sms_history(db_session, sample_student_user, limit=10)
    assert len(history) == 1
    assert "مصاحبه" in history[0]["message"]
    assert sim.student_sms_history_available()


@pytest.mark.asyncio
async def test_list_student_sms_history_includes_dismissed(
    db_session, sms_log_with_ui, sample_student_user,
):
    from app.models.operational_models import SmsSimulationDismissal

    mine = "09123334455"
    sample_student_user.phone = mine
    await db_session.commit()
    row_id = uuid.uuid4()
    db_session.add(
        SmsSimulationOutbox(
            id=row_id,
            phone=mine,
            message="یادآوری پرداخت",
            kind="notification",
            template_key="payment_overdue",
        )
    )
    await db_session.commit()
    db_session.add(
        SmsSimulationDismissal(
            sms_id=row_id,
            user_id=sample_student_user.id,
        )
    )
    await db_session.commit()

    history = await sim.list_student_sms_history(db_session, sample_student_user, limit=10)
    assert len(history) == 1
    assert history[0]["id"] == str(row_id)


def test_simulation_popup_enabled_with_mirror(monkeypatch, sms_real_provider):
    monkeypatch.setenv("SMS_SIMULATION_MIRROR_REAL_SEND", "true")
    _reload_sms_settings()
    assert sim.simulation_popup_enabled()
    assert not sim.simulation_recording_enabled()
