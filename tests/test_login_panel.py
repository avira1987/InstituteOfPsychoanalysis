"""
تست هر دو مدل ورود به پنل کاربری:
۱) ورود با نام کاربری و رمز عبور (login-challenge + login-json)
۲) ورود با پیامک (OTP: request + verify)
"""

import re
from unittest.mock import patch

import pytest
from starlette.testclient import TestClient

from app.main import app


def _parse_challenge_answer(question: str) -> str | None:
    """از متن سوال چالش (مثلاً «حاصل ۷ + ۴ چند می‌شود؟») عدد پاسخ را استخراج می‌کند."""
    m = re.search(r"حاصل\s*(\d+)\s*\+\s*(\d+)", question)
    if m:
        return str(int(m.group(1)) + int(m.group(2)))
    return None


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


from app.demo_role_users import resolve_portal_login_username


def test_resolve_portal_login_username_accepts_role_without_suffix():
    assert resolve_portal_login_username("deputy_education") == "deputy_education1"
    assert resolve_portal_login_username("deputy_education1") == "deputy_education1"
    assert resolve_portal_login_username("admin") == "admin"
    assert resolve_portal_login_username("staff") == "staff1"
    assert resolve_portal_login_username("staf1") == "staff1"
    assert resolve_portal_login_username("dakheli") == "dakheli1"
    assert resolve_portal_login_username("dakheli1") == "dakheli1"
    assert resolve_portal_login_username("admissions_officer") == "demo_admissions"
    assert resolve_portal_login_username("admissions_officer1") == "demo_admissions"
    assert resolve_portal_login_username("demo_admissions") == "demo_admissions"
    assert resolve_portal_login_username("deputy_education_director") == "deputy_education1"
    assert resolve_portal_login_username("deputy_education_director1") == "deputy_education1"


def test_login_password_and_access_panel(client: TestClient):
    """
    ورود با نام کاربری و رمز عبور و دسترسی به پنل:
    دریافت چالش -> ارسال login-json با پاسخ چالش -> دریافت توکن -> فراخوانی /api/auth/me
    """
    r_challenge = client.post("/api/auth/login-challenge")
    assert r_challenge.status_code == 200, f"login-challenge failed: {r_challenge.text}"
    data_challenge = r_challenge.json()
    challenge_id = data_challenge.get("challenge_id")
    question = data_challenge.get("question", "")
    assert challenge_id and question, "challenge_id and question required"

    answer = _parse_challenge_answer(question)
    assert answer is not None, f"Could not parse challenge answer from: {question}"

    r_login = client.post(
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

    r_me = client.get(
        "/api/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r_me.status_code == 200, f"auth/me failed: {r_me.text}"
    me = r_me.json()
    assert me.get("username") == "admin"
    assert "role" in me


def test_login_otp_and_access_panel(client: TestClient):
    """
    ورود با پیامک (OTP) و دسترسی به پنل:
    درخواست کد -> تأیید با dev_code -> فراخوانی /api/auth/me
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
        phone = "09123456789"

        r_request = client.post(
            "/api/auth/otp/request",
            json={"phone": phone},
        )
        assert r_request.status_code == 200, f"otp/request failed: {r_request.text}"
        data_request = r_request.json()
        assert data_request.get("success") is True, data_request.get("error", "unknown error")

        dev_code = data_request.get("dev_code")
        assert dev_code, "dev_code expected in OTP request response (patch adds it from DB if needed)"

        r_verify = client.post(
            "/api/auth/otp/verify",
            json={"phone": phone, "code": dev_code},
        )
        assert r_verify.status_code == 200, f"otp/verify failed: {r_verify.text}"
        data_verify = r_verify.json()
        assert data_verify.get("success") is True, data_verify.get("error", "unknown error")
        token = data_verify.get("access_token")
        assert token, "access_token expected in OTP verify response"

        r_me = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r_me.status_code == 200, f"auth/me failed: {r_me.text}"
        me = r_me.json()
        assert "username" in me
        assert me.get("username", "").startswith("user_") or "role" in me


def test_login_password_accepts_persian_digits(client: TestClient):
    """رمز و پاسخ کد امنیتی با ارقام فارسی باید پذیرفته شوند."""
    r_challenge = client.post("/api/auth/login-challenge")
    assert r_challenge.status_code == 200
    data = r_challenge.json()
    answer_latin = _parse_challenge_answer(data["question"])
    assert answer_latin is not None
    answer_fa = answer_latin.translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

    r_login = client.post(
        "/api/auth/login-json",
        json={
            "username": "admin",
            "password": "admin" + "۱۲۳",
            "challenge_id": data["challenge_id"],
            "challenge_answer": answer_fa,
        },
    )
    assert r_login.status_code == 200, f"login-json failed: {r_login.text}"


def test_login_password_wrong_credentials(client: TestClient):
    """ورود با نام کاربری یا رمز عبور اشتباه: باید 401 برگردد."""
    r_challenge = client.post("/api/auth/login-challenge")
    assert r_challenge.status_code == 200
    data = r_challenge.json()
    challenge_id = data["challenge_id"]
    answer = _parse_challenge_answer(data["question"])
    assert answer is not None

    r_login = client.post(
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


def test_login_otp_wrong_code(client: TestClient):
    """ورود با کد OTP اشتباه: باید خطا برگردد و توکن داده نشود."""
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
        phone = "09121111111"

        r_request = client.post("/api/auth/otp/request", json={"phone": phone})
        assert r_request.status_code == 200
        assert r_request.json().get("success") is True

        r_verify = client.post(
            "/api/auth/otp/verify",
            json={"phone": phone, "code": "000000"},
        )
        assert r_verify.status_code == 400, f"Expected 400 for wrong OTP code, got {r_verify.status_code}"
        data = r_verify.json()
        assert "detail" in data or "error" in data
        assert "access_token" not in data
