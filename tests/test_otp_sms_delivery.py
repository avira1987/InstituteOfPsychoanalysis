"""
تشخیص مسیر پیامک OTP ورود — شمارهٔ گزارش‌شده 09177101053 و پترن ملی‌پیامک.

علت‌های رایج «پیامک اشتباه» یا کد نامعتبر:
- پترن bodyId اشتباه (مثلاً خوش‌آمد دو‌متغیره به‌جای کد ورود تک‌متغیره)
- fallback به SendOtp با قالب پیش‌فرض پنل (متفاوت از کد ذخیره‌شده در DB اگر پیکربندی نشده باشد)
- درخواست مجدد OTP که کد قبلی را باطل می‌کند
- ناهماهنگی نرمال‌سازی شماره بین درخواست و تأیید
"""

from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.otp_service as otp_service
import app.services.sms_gateway as sms_gateway
from app.config import get_settings
from app.services.melipayamak_pattern_catalog import get_pattern_by_body_id
from app.api.auth import get_password_hash
from app.models.operational_models import User
from app.services.otp_service import (
    find_user_by_login_phone,
    normalize_otp_code,
    verify_otp,
)
from app.services.sms_gateway import normalize_ir_mobile, send_otp_sms

REPORTED_PHONE = "09177101053"
REPORTED_PHONE_NORMALIZED = "09177101053"
DEFAULT_OTP_PATTERN_BODY_ID = 449667
WELCOME_PATTERN_BODY_ID = 450373


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("09177101053", REPORTED_PHONE_NORMALIZED),
        ("۰۹۱۷۷۱۰۱۰۵۳", REPORTED_PHONE_NORMALIZED),
        ("+989177101053", REPORTED_PHONE_NORMALIZED),
        ("00989177101053", REPORTED_PHONE_NORMALIZED),
        ("989177101053", REPORTED_PHONE_NORMALIZED),
        (" 09 17 710 10 53 ", REPORTED_PHONE_NORMALIZED),
    ],
)
def test_reported_phone_normalizes_consistently(raw: str, expected: str):
    assert normalize_ir_mobile(raw) == expected
    assert re.fullmatch(r"09\d{9}", normalize_ir_mobile(raw))


def test_otp_pattern_catalog_is_single_variable_login():
    pat = get_pattern_by_body_id(DEFAULT_OTP_PATTERN_BODY_ID)
    assert pat is not None, "پترن 449667 باید در metadata/melipayamak_patterns.json باشد"
    assert pat.get("variableCount") == 1
    assert "کد ورود" in (pat.get("templateText") or "")
    assert "{0}" in (pat.get("templateText") or "")


def test_welcome_pattern_must_not_be_used_as_otp_body_id():
    """اگر SMS_OTP_PATTERN_BODY_ID اشتباهی 450373 باشد، فقط یک مقدار (کد) به پترن دو‌اسلاتی می‌رود."""
    welcome = get_pattern_by_body_id(WELCOME_PATTERN_BODY_ID)
    otp_pat = get_pattern_by_body_id(DEFAULT_OTP_PATTERN_BODY_ID)
    assert welcome and otp_pat
    assert int(welcome["variableCount"]) >= 2
    assert int(otp_pat["variableCount"]) == 1
    settings = get_settings()
    configured = int(getattr(settings, "SMS_OTP_PATTERN_BODY_ID", 0) or 0)
    if configured > 0:
        assert configured != WELCOME_PATTERN_BODY_ID, (
            "SMS_OTP_PATTERN_BODY_ID نباید bodyId خوش‌آمد (450373) باشد؛ "
            "پیامک ورود با قالب نام کاربری/رمز جایگزین می‌شود."
        )


def test_otp_login_sms_body_contains_code():
    code = "482917"
    body = sms_gateway._otp_login_sms_body_fa(code)
    assert code in body
    assert "کد ورود" in body


@pytest.mark.asyncio
async def test_send_otp_sms_pattern_sends_only_six_digit_code_not_full_text():
    """مسیر پترن: text فقط همان کد است تا در پنل «کد ورود: {0} میباشد» درست پر شود."""
    captured: dict = {}

    async def fake_pattern(phone: str, body_id: int, pattern_text: str) -> dict:
        captured["phone"] = phone
        captured["body_id"] = body_id
        captured["pattern_text"] = pattern_text
        return {"success": True, "provider": "mellipayamak_pattern"}

    old_settings = sms_gateway.settings
    mock_settings = MagicMock()
    mock_settings.SMS_PROVIDER = "mellipayamak"
    mock_settings.SMS_USERNAME = "u"
    mock_settings.SMS_PASSWORD = "p"
    mock_settings.SMS_API_KEY = ""
    mock_settings.SMS_OTP_PATTERN_BODY_ID = DEFAULT_OTP_PATTERN_BODY_ID
    sms_gateway.settings = mock_settings

    code = "391204"
    try:
        with patch.object(sms_gateway, "send_sms_pattern", side_effect=fake_pattern):
            with patch.object(
                sms_gateway, "_send_mellipayamak_rest_classic", new_callable=AsyncMock
            ) as classic:
                with patch.object(
                    sms_gateway, "_send_mellipayamak_otp_rest", new_callable=AsyncMock
                ) as send_otp:
                    result = await send_otp_sms(REPORTED_PHONE, code)
    finally:
        sms_gateway.settings = old_settings

    assert result["success"] is True
    assert captured["phone"] == REPORTED_PHONE_NORMALIZED
    assert captured["body_id"] == DEFAULT_OTP_PATTERN_BODY_ID
    assert captured["pattern_text"] == code
    assert ";" not in captured["pattern_text"]
    assert "کد ورود" not in captured["pattern_text"]
    classic.assert_not_called()
    send_otp.assert_not_called()


@pytest.mark.asyncio
async def test_send_otp_sms_misconfigured_welcome_body_id_produces_wrong_pattern_payload():
    """شبیه‌سازی bodyId اشتباه: یک اسلات پر می‌شود، دومی خالی — پیامک در گوشی نامفهوم/«اشتباه» به نظر می‌رسد."""
    captured: dict = {}

    async def fake_pattern(phone: str, body_id: int, pattern_text: str) -> dict:
        captured["body_id"] = body_id
        captured["pattern_text"] = pattern_text
        return {"success": True, "provider": "mellipayamak_pattern"}

    old_settings = sms_gateway.settings
    mock_settings = MagicMock()
    mock_settings.SMS_PROVIDER = "mellipayamak"
    mock_settings.SMS_USERNAME = "u"
    mock_settings.SMS_PASSWORD = "p"
    mock_settings.SMS_API_KEY = ""
    mock_settings.SMS_OTP_PATTERN_BODY_ID = WELCOME_PATTERN_BODY_ID
    sms_gateway.settings = mock_settings

    code = "482917"
    try:
        with patch.object(sms_gateway, "send_sms_pattern", side_effect=fake_pattern):
            await send_otp_sms(REPORTED_PHONE, code)
    finally:
        sms_gateway.settings = old_settings

    assert captured["body_id"] == WELCOME_PATTERN_BODY_ID
    assert captured["pattern_text"] == code
    welcome = get_pattern_by_body_id(WELCOME_PATTERN_BODY_ID)
    slots = int(welcome.get("variableCount") or 0)
    assert slots >= 2
    assert ";" not in captured["pattern_text"]


@pytest.mark.asyncio
async def test_request_otp_stores_same_code_sent_to_sms_gateway():
    from app.models.operational_models import OTPCode

    sent_codes: list[str] = []

    async def capture_send(phone: str, code: str) -> dict:
        sent_codes.append(code)
        return {"success": True, "provider": "log"}

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    with patch.object(otp_service, "send_otp_sms", side_effect=capture_send):
        with patch.object(
            otp_service.sms_simulation,
            "record_simulated_sms_in_request_session",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with patch.object(otp_service, "_generate_code", return_value="771053"):
                result = await otp_service.request_otp(mock_db, REPORTED_PHONE)

    assert result["success"] is True
    assert len(sent_codes) == 1
    assert sent_codes[0] == "771053"
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, OTPCode)
    assert added.phone == REPORTED_PHONE_NORMALIZED
    assert added.code == sent_codes[0]


@pytest.mark.asyncio
async def test_request_otp_blocks_unknown_phone_when_public_signup_closed():
    mock_db = AsyncMock()
    settings = MagicMock()
    settings.OTP_RESTRICT_TO_STUDENT_PHONES = True
    settings.ALLOW_PUBLIC_OTP_SIGNUP = False
    with patch.object(otp_service, "get_settings", return_value=settings):
        with patch.object(
            otp_service, "find_user_by_login_phone", new_callable=AsyncMock, return_value=None
        ):
            result = await otp_service.request_otp(mock_db, REPORTED_PHONE)
    assert result["success"] is False
    assert "ثبت نشده" in result["error"]


@pytest.mark.asyncio
async def test_request_otp_allows_unknown_phone_when_public_signup_open():
    from app.models.operational_models import OTPCode

    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    settings = MagicMock()
    settings.OTP_RESTRICT_TO_STUDENT_PHONES = True
    settings.ALLOW_PUBLIC_OTP_SIGNUP = True
    settings.SMS_PROVIDER = "log"
    settings.SMS_SIMULATION_UI = False
    settings.OTP_SHOW_CODE_IN_UI = False
    settings.SECRET_KEY = "test-secret-key-for-otp-hmac"

    with patch.object(otp_service, "get_settings", return_value=settings):
        with patch.object(
            otp_service, "find_user_by_login_phone", new_callable=AsyncMock, return_value=None
        ):
            with patch.object(
                otp_service, "send_otp_sms", new_callable=AsyncMock, return_value={"success": True, "provider": "log"}
            ):
                with patch.object(
                    otp_service.sms_simulation,
                    "record_simulated_sms_in_request_session",
                    new_callable=AsyncMock,
                    return_value=None,
                ):
                    result = await otp_service.request_otp(mock_db, REPORTED_PHONE)

    assert result["success"] is True
    added = mock_db.add.call_args[0][0]
    assert isinstance(added, OTPCode)
    assert added.phone == REPORTED_PHONE_NORMALIZED


@pytest.mark.asyncio
async def test_request_otp_does_not_send_welcome_sms_on_request():
    mock_db = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()
    mock_db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )

    with patch.object(otp_service, "send_otp_sms", new_callable=AsyncMock, return_value={"success": True}):
        with patch.object(
            otp_service.sms_simulation,
            "record_simulated_sms_in_request_session",
            new_callable=AsyncMock,
            return_value=None,
        ):
            with patch.object(otp_service, "send_sms", new_callable=AsyncMock) as welcome:
                await otp_service.request_otp(mock_db, REPORTED_PHONE)
    welcome.assert_not_called()


def test_normalize_otp_code_accepts_persian_digits_like_sms():
    assert normalize_otp_code("۷۷۱۰۵۳") == "771053"
    assert normalize_otp_code("۰۴۸۲۹۱") == "048291"
    assert normalize_otp_code(" 482 917 ") == "482917"


@pytest.mark.asyncio
async def test_resend_otp_invalidates_previous_code_for_same_phone(db_session):
    """دو درخواست پشت‌سرهم: فقط کد آخر معتبر است — پیامک دیررس «اشتباه» به نظر می‌رسد."""
    from sqlalchemy import select

    from app.models.operational_models import OTPCode

    codes_sent: list[str] = []
    seq = iter(["111111", "222222"])

    async def fake_send(phone: str, code: str) -> dict:
        codes_sent.append(code)
        return {"success": True, "provider": "log"}

    with patch.object(otp_service, "send_otp_sms", side_effect=fake_send):
        with patch.object(otp_service, "_generate_code", side_effect=lambda: next(seq)):
            r1 = await otp_service.request_otp(db_session, REPORTED_PHONE)
            r2 = await otp_service.request_otp(db_session, REPORTED_PHONE)

    assert r1["success"] and r2["success"]
    assert codes_sent == ["111111", "222222"]

    row = (
        await db_session.execute(
            select(OTPCode)
            .where(OTPCode.phone == REPORTED_PHONE_NORMALIZED, OTPCode.is_used.is_(False))
            .order_by(OTPCode.created_at.desc())
        )
    ).scalars().first()
    assert row is not None
    assert row.code == "222222"

    bad = await otp_service.verify_otp(db_session, REPORTED_PHONE, "111111")
    assert bad["success"] is False
    assert "صحیح نیست" in bad.get("error", "") or "نامعتبر" in bad.get("error", "")


@pytest.mark.asyncio
async def test_find_user_by_login_phone_legacy_plus98(db_session):
    """شماره در DB به صورت +98… ذخیره شده؛ OTP با 09… باید همان کاربر را پیدا کند."""
    import uuid

    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username=f"legacy_{uid.hex[:8]}",
            phone="+989177101053",
            hashed_password=get_password_hash("x"),
            role="student",
            is_active=True,
        )
    )
    await db_session.commit()

    found = await find_user_by_login_phone(db_session, REPORTED_PHONE)
    assert found is not None
    assert found.id == uid


@pytest.mark.asyncio
async def test_find_user_by_login_phone_when_only_username_is_mobile(db_session):
    """phone خالی ولی username همان موبایل — سناریوی رایج ثبت دستی."""
    import uuid

    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username=REPORTED_PHONE_NORMALIZED,
            phone=None,
            hashed_password=get_password_hash("x"),
            role="student",
            is_active=True,
        )
    )
    await db_session.commit()

    found = await find_user_by_login_phone(db_session, REPORTED_PHONE)
    assert found is not None
    assert found.id == uid


@pytest.mark.asyncio
async def test_verify_otp_rejects_stale_code_when_newer_otp_exists(db_session):
    """دو کد فعال (race): کد قدیمی‌تر رد می‌شود حتی اگر هنوز منقضی نشده باشد."""
    import uuid
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.models.operational_models import OTPCode

    now = datetime.now(timezone.utc)
    db_session.add_all(
        [
            OTPCode(
                id=uuid.uuid4(),
                phone=REPORTED_PHONE_NORMALIZED,
                code="111111",
                expires_at=now + timedelta(seconds=120),
                created_at=now - timedelta(seconds=30),
            ),
            OTPCode(
                id=uuid.uuid4(),
                phone=REPORTED_PHONE_NORMALIZED,
                code="222222",
                expires_at=now + timedelta(seconds=120),
                created_at=now,
            ),
        ]
    )
    await db_session.commit()

    result = await verify_otp(db_session, REPORTED_PHONE, "111111")
    assert result["success"] is False
    assert "آخرین" in result.get("error", "")

    rows = (
        await db_session.execute(
            select(OTPCode).where(OTPCode.phone == REPORTED_PHONE_NORMALIZED)
        )
    ).scalars().all()
    assert all(not r.is_used for r in rows)


@pytest.mark.asyncio
async def test_verify_otp_rejects_inactive_user_even_with_valid_code(db_session):
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.models.operational_models import OTPCode

    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username=REPORTED_PHONE_NORMALIZED,
            phone=REPORTED_PHONE_NORMALIZED,
            hashed_password=get_password_hash("x"),
            role="student",
            is_active=False,
        )
    )
    now = datetime.now(timezone.utc)
    db_session.add(
        OTPCode(
            id=uuid.uuid4(),
            phone=REPORTED_PHONE_NORMALIZED,
            code="551103",
            expires_at=now + timedelta(seconds=120),
        )
    )
    await db_session.commit()

    with patch.object(otp_service, "send_sms", new_callable=AsyncMock):
        result = await verify_otp(db_session, REPORTED_PHONE, "551103")
    assert result["success"] is False
    assert "غیرفعال" in result.get("error", "")


@pytest.mark.asyncio
async def test_verify_otp_syncs_legacy_phone_then_issues_token(db_session):
    import uuid
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.models.operational_models import OTPCode

    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username=REPORTED_PHONE_NORMALIZED,
            phone="+989177101053",
            hashed_password=get_password_hash("x"),
            role="student",
            is_active=True,
            portal_password_plain="already",
        )
    )
    now = datetime.now(timezone.utc)
    db_session.add(
        OTPCode(
            id=uuid.uuid4(),
            phone=REPORTED_PHONE_NORMALIZED,
            code="771053",
            expires_at=now + timedelta(seconds=120),
        )
    )
    await db_session.commit()

    with patch.object(otp_service, "send_sms", new_callable=AsyncMock):
        result = await verify_otp(db_session, REPORTED_PHONE, "771053")
    assert result["success"] is True
    assert result.get("access_token")

    row = (await db_session.execute(select(User).where(User.id == uid))).scalar_one()
    assert row.phone == REPORTED_PHONE_NORMALIZED


@pytest.mark.asyncio
async def test_verify_otp_inactive_user_does_not_consume_code(db_session):
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.models.operational_models import OTPCode

    uid = uuid.uuid4()
    db_session.add(
        User(
            id=uid,
            username=REPORTED_PHONE_NORMALIZED,
            phone=REPORTED_PHONE_NORMALIZED,
            hashed_password=get_password_hash("x"),
            role="student",
            is_active=False,
        )
    )
    now = datetime.now(timezone.utc)
    db_session.add(
        OTPCode(
            id=uuid.uuid4(),
            phone=REPORTED_PHONE_NORMALIZED,
            code="903317",
            expires_at=now + timedelta(seconds=120),
        )
    )
    await db_session.commit()

    from sqlalchemy import select

    result = await verify_otp(db_session, REPORTED_PHONE, "903317")
    assert result["success"] is False
    assert "غیرفعال" in result.get("error", "")

    row = (
        await db_session.execute(
            select(OTPCode).where(
                OTPCode.phone == REPORTED_PHONE_NORMALIZED,
                OTPCode.code == "903317",
            )
        )
    ).scalar_one()
    assert row.is_used is False
