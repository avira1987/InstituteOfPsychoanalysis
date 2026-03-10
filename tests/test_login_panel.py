"""
تست هر دو مدل ورود به پنل کاربری:
۱) ورود با نام کاربری و رمز عبور (login-challenge + login-json)
۲) ورود با پیامک (OTP: request + verify)
"""

import re
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app


def _parse_challenge_answer(question: str) -> str | None:
    """از متن سوال چالش (مثلاً «حاصل ۷ + ۴ چند می‌شود؟») عدد پاسخ را استخراج می‌کند."""
    m = re.search(r"حاصل\s*(\d+)\s*\+\s*(\d+)", question)
    if m:
        return str(int(m.group(1)) + int(m.group(2)))
    return None


@pytest.mark.asyncio
async def test_login_password_and_access_panel():
    """
    ورود با نام کاربری و رمز عبور و دسترسی به پنل:
    دریافت چالش -> ارسال login-json با پاسخ چالش -> دریافت توکن -> فراخوانی /api/auth/me
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # ۱) دریافت چالش ورود
        r_challenge = await client.post("/api/auth/login-challenge")
        assert r_challenge.status_code == 200, f"login-challenge failed: {r_challenge.text}"
        data_challenge = r_challenge.json()
        challenge_id = data_challenge.get("challenge_id")
        question = data_challenge.get("question", "")
        assert challenge_id and question, "challenge_id and question required"

        answer = _parse_challenge_answer(question)
        assert answer is not None, f"Could not parse challenge answer from: {question}"

        # ۲) ورود با نام کاربری و رمز عبور
        r_login = await client.post(
            "/api/auth/login-json",
            json={
                "username": "admin",
                "password": "admin123",
                "challenge_id": challenge_id,
                "challenge_answer": answer,
            },
        )
        assert r_login.status_code == 200, f"login-json failed: {r_login.text}"
        token_data = r_login.json()
        assert "access_token" in token_data
        token = token_data["access_token"]

        # ۳) دسترسی به پنل (دریافت اطلاعات کاربر جاری)
        r_me = await client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_me.status_code == 200, f"auth/me failed: {r_me.text}"
        me = r_me.json()
        assert me.get("username") == "admin"
        assert "role" in me


@pytest.mark.asyncio
async def test_login_otp_and_access_panel():
    """
    ورود با پیامک (OTP) و دسترسی به پنل:
    درخواست کد -> تأیید با dev_code -> فراخوانی /api/auth/me
    با patch اطمینان حاصل می‌کنیم که پاسخ request حاوی dev_code است (مثل حالت DEBUG + log).
    """
    from app.services import otp_service
    from app.models.operational_models import OTPCode
    from sqlalchemy import select

    real_request_otp = otp_service.request_otp

    async def _request_otp_with_dev_code(db, phone: str):
        result = await real_request_otp(db, phone)
        if result.get("success") and "dev_code" not in result:
            r = await db.execute(
                select(OTPCode)
                .where(OTPCode.phone == phone.strip().replace(" ", ""))
                .order_by(OTPCode.created_at.desc())
                .limit(1)
            )
            row = r.scalars().first()
            if row:
                result["dev_code"] = row.code
        return result

    with patch.object(otp_service, "request_otp", side_effect=_request_otp_with_dev_code):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            phone = "09123456789"

            # ۱) درخواست ارسال کد OTP
            r_request = await client.post(
                "/api/auth/otp/request",
                json={"phone": phone},
            )
            assert r_request.status_code == 200, f"otp/request failed: {r_request.text}"
            data_request = r_request.json()
            assert data_request.get("success") is True, data_request.get("error", "unknown error")

            dev_code = data_request.get("dev_code")
            assert dev_code, "dev_code expected in OTP request response (patch adds it from DB if needed)"

            # ۲) تأیید کد و دریافت توکن
            r_verify = await client.post(
                "/api/auth/otp/verify",
                json={"phone": phone, "code": dev_code},
            )
            assert r_verify.status_code == 200, f"otp/verify failed: {r_verify.text}"
            data_verify = r_verify.json()
            assert data_verify.get("success") is True, data_verify.get("error", "unknown error")
            token = data_verify.get("access_token")
            assert token, "access_token expected in OTP verify response"

            # ۳) دسترسی به پنل (دریافت اطلاعات کاربر جاری)
            r_me = await client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            assert r_me.status_code == 200, f"auth/me failed: {r_me.text}"
            me = r_me.json()
            assert "username" in me
            assert me.get("username", "").startswith("user_") or "role" in me


# ─── تست با اطلاعات اشتباه (باید خطا برگردد و توکن داده نشود) ─────────────────

@pytest.mark.asyncio
async def test_login_password_wrong_credentials():
    """
    ورود با نام کاربری یا رمز عبور اشتباه: باید 401 برگردد و پیام خطا داشته باشد، توکن داده نشود.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r_challenge = await client.post("/api/auth/login-challenge")
        assert r_challenge.status_code == 200
        data = r_challenge.json()
        challenge_id = data["challenge_id"]
        answer = _parse_challenge_answer(data["question"])
        assert answer is not None

        # رمز عبور اشتباه
        r_login = await client.post(
            "/api/auth/login-json",
            json={
                "username": "admin",
                "password": "wrong_password_123",
                "challenge_id": challenge_id,
                "challenge_answer": answer,
            },
        )
        assert r_login.status_code == 401, f"Expected 401 for wrong password, got {r_login.status_code}"
        body = r_login.json()
        assert "detail" in body
        assert "access_token" not in body


@pytest.mark.asyncio
async def test_login_otp_wrong_code():
    """
    ورود با کد OTP اشتباه: باید خطا برگردد و توکن داده نشود.
    """
    from app.services import otp_service
    from app.models.operational_models import OTPCode
    from sqlalchemy import select

    real_request_otp = otp_service.request_otp

    async def _request_otp_with_dev_code(db, phone: str):
        result = await real_request_otp(db, phone)
        if result.get("success") and "dev_code" not in result:
            r = await db.execute(
                select(OTPCode)
                .where(OTPCode.phone == phone.strip().replace(" ", ""))
                .order_by(OTPCode.created_at.desc())
                .limit(1)
            )
            row = r.scalars().first()
            if row:
                result["dev_code"] = row.code
        return result

    with patch.object(otp_service, "request_otp", side_effect=_request_otp_with_dev_code):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            phone = "09121111111"

            r_request = await client.post("/api/auth/otp/request", json={"phone": phone})
            assert r_request.status_code == 200
            assert r_request.json().get("success") is True

            # کد اشتباه (مثلاً 000000)
            r_verify = await client.post(
                "/api/auth/otp/verify",
                json={"phone": phone, "code": "000000"},
            )
            assert r_verify.status_code == 400, f"Expected 400 for wrong OTP code, got {r_verify.status_code}"
            data = r_verify.json()
            # FastAPI معمولاً خطا را در detail برمی‌گرداند
            assert "detail" in data or "error" in data
            assert "access_token" not in data
