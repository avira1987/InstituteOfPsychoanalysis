"""HTTP API — پاپ‌آپ پیامک شبیه‌سازی‌شده باید از پاسخ endpointها قابل دریافت باشد."""

import random
import uuid

import pytest
from starlette.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.services import sms_gateway as sg
from app.services import sms_simulation_service as sim


def _reload_sms_settings() -> None:
    get_settings.cache_clear()
    sg.settings = get_settings()


def _random_mobile() -> str:
    return "09" + "".join(random.choice("0123456789") for _ in range(9))


@pytest.fixture
def sms_log_client(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "log")
    monkeypatch.setenv("SMS_SIMULATION_UI", "true")
    monkeypatch.setenv("SMS_SIMULATION_POPUP_SHOW_ALL", "true")
    monkeypatch.setenv("OTP_RESTRICT_TO_STUDENT_PHONES", "false")
    _reload_sms_settings()
    with TestClient(app) as client:
        yield client
    get_settings.cache_clear()
    sg.settings = get_settings()


def _admin_headers(client: TestClient) -> dict:
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_public_sms_simulation_status(sms_log_client: TestClient):
    r = sms_log_client.get("/api/public/sms-simulation-status")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("enabled") is True
    assert data.get("provider") == "log"


def test_otp_request_api_returns_simulated_sms(sms_log_client: TestClient):
    phone = _random_mobile()
    r = sms_log_client.post("/api/auth/otp/request", json={"phone": phone})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    simsms = data.get("simulated_sms")
    assert simsms is not None, "simulated_sms باید در پاسخ OTP باشد (SMS_PROVIDER=log + SMS_SIMULATION_UI=true)"
    assert simsms.get("phone") == phone
    assert simsms.get("message")
    assert "کد ورود" in simsms["message"]


def test_admin_test_sms_returns_simulated_sms(sms_log_client: TestClient):
    headers = _admin_headers(sms_log_client)
    phone = _random_mobile()
    r = sms_log_client.post(
        "/api/admin/test-sms",
        headers=headers,
        json={"phone": phone, "message": "تست پاپ‌آپ API"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("success") is True
    assert data.get("provider") == "log"
    simsms = data.get("simulated_sms")
    sms_list = data.get("simulated_sms_list") or []
    assert simsms is not None or len(sms_list) >= 1, "test-sms باید simulated_sms برگرداند"
    entry = simsms or sms_list[0]
    assert entry.get("phone") == phone
    assert "تست پاپ‌آپ" in entry.get("message", "")


def test_panel_simulated_sms_enabled_for_admin(sms_log_client: TestClient):
    headers = _admin_headers(sms_log_client)
    phone = _random_mobile()
    send = sms_log_client.post(
        "/api/admin/test-sms",
        headers=headers,
        json={"phone": phone, "message": "برای polling پنل"},
    )
    assert send.status_code == 200, send.text

    r = sms_log_client.get("/api/panel/simulated-sms", headers=headers, params={"limit": 50})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("enabled") is True, "enabled باید true باشد در حالت log"
    assert body.get("feed_scope") == "global_all_recipients"
    items = body.get("items") or []
    phones = {x.get("phone") for x in items}
    assert phone in phones


@pytest.mark.asyncio
async def test_capture_batch_via_test_sms_api(sms_log_client: TestClient):
    headers = _admin_headers(sms_log_client)
    phone = _random_mobile()
    r = sms_log_client.post(
        "/api/admin/test-sms",
        headers=headers,
        json={"phone": phone, "message": "capture via API"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    sms_list = data.get("simulated_sms_list") or []
    assert len(sms_list) >= 1
    assert sms_list[0].get("message") == "capture via API"


def test_capture_contextvar_unit():
    sim.begin_capture()
    sim._emit_capture(
        {"id": "unit-1", "phone": "09120001111", "message": "ctx", "kind": "free_text"}
    )
    got = sim.drain_capture()
    assert len(got) == 1
    assert got[0]["message"] == "ctx"


def test_merge_simulated_sms_into_payload_dedupes():
    from app.middleware.sms_simulation_capture import merge_simulated_sms_into_payload

    entry = {"id": "a1", "phone": "09120001111", "message": "سلام", "kind": "free_text"}
    data = {"success": True, "simulated_sms_list": [entry], "simulated_sms": entry}
    captured = [dict(entry)]
    merged = merge_simulated_sms_into_payload(data, captured)
    assert len(merged["simulated_sms_list"]) == 1


def test_merge_simulated_sms_appends_new():
    from app.middleware.sms_simulation_capture import merge_simulated_sms_into_payload

    data = {"ok": True}
    captured = [{"id": "b2", "phone": "09123334444", "message": "جدید", "kind": "notification"}]
    merged = merge_simulated_sms_into_payload(data, captured)
    assert merged["simulated_sms"]["message"] == "جدید"
    assert len(merged["simulated_sms_list"]) == 1


def test_resolve_sms_message_body_pattern_fallback():
    from app.services.notification_service import resolve_sms_message_body

    body = resolve_sms_message_body("interview_details_applicant", {"student_name": "علی"})
    assert "interview_details_applicant" in body or "علی" in body or "پترن" in body


def test_panel_student_sms_history_enabled(sms_log_client: TestClient):
    headers = _admin_headers(sms_log_client)
    phone = _random_mobile()
    send = sms_log_client.post(
        "/api/admin/test-sms",
        headers=headers,
        json={"phone": phone, "message": "پیامک تاریخچه دانشجو"},
    )
    assert send.status_code == 200, send.text

    r = sms_log_client.get("/api/panel/student-sms-history", headers=headers, params={"limit": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("enabled") is True
    # admin شماره inbox ندارد — لیست خالی ولی enabled باید true باشد
    assert isinstance(body.get("items"), list)


def test_simulation_disabled_no_simulated_sms_in_otp(monkeypatch):
    monkeypatch.setenv("SMS_PROVIDER", "log")
    monkeypatch.setenv("SMS_SIMULATION_UI", "false")
    _reload_sms_settings()
    with TestClient(app) as client:
        phone = _random_mobile()
        r = client.post("/api/auth/otp/request", json={"phone": phone})
        assert r.status_code == 200, r.text
        assert r.json().get("simulated_sms") is None
    monkeypatch.setenv("SMS_SIMULATION_UI", "true")
    _reload_sms_settings()
