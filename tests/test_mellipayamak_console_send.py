"""تست مسیر کنسول ملی‌پیامک: توکن در مسیر URL (مطابق node-melipayamak)، نه Bearer.

مقادیر SMS_API_KEY و SMS_LINE_NUMBER از .env (از طریق pydantic get_settings) خوانده می‌شود.
اگر SMS_API_KEY خالی باشد تست رد می‌شود (skip).
"""

import json

import httpx
import pytest
import respx

import app.services.sms_gateway as sms_gateway
from app.config import get_settings


@pytest.fixture
def mellipayamak_console_settings_from_env():
    """هم‌تراز کردن sms_gateway.settings با همان Settings که از .env بارگذاری می‌شود."""
    old = sms_gateway.settings
    get_settings.cache_clear()
    sms_gateway.settings = get_settings()
    yield
    sms_gateway.settings = old
    get_settings.cache_clear()


@pytest.mark.asyncio
@respx.mock
async def test_console_send_posts_to_path_with_token_not_bearer(mellipayamak_console_settings_from_env):
    token = (sms_gateway.settings.SMS_API_KEY or "").strip()
    if not token:
        pytest.skip("SMS_API_KEY در .env تنظیم نشده")

    line = (sms_gateway.settings.SMS_LINE_NUMBER or "").strip()
    expected_url = f"https://console.melipayamak.com/api/send/simple/{token}"

    route = respx.post(expected_url).mock(
        return_value=httpx.Response(200, json={"recId": "999", "status": ""})
    )

    result = await sms_gateway._send_mellipayamak("09123456789", "hello")

    assert result["success"] is True
    assert result.get("provider") == "mellipayamak"
    assert route.called
    sent = route.calls[0].request
    assert sent.headers.get("Authorization") is None
    body = json.loads(sent.content.decode())
    assert body["to"] == "09123456789"
    assert body["text"] == "hello"
    if line:
        assert body.get("from") == line
    else:
        assert "from" not in body


@pytest.mark.parametrize(
    "payload,ok",
    [
        ({"recId": "1"}, True),
        ({"recIds": ["1", "2"]}, True),
        ({"status": "خطا"}, False),
        ({}, False),
    ],
)
def test_mellipayamak_console_response_ok(payload, ok):
    assert sms_gateway._mellipayamak_console_response_ok(payload) is ok


def test_payamak_rest_send_sms_response_ok_allow_send():
    """پاسخ واقعی SendSMS: Value>0 یعنی موفق حتی با RetStatus غیر از 1 (مثلاً 9 + AllowSend)."""
    payload = {"Value": "6", "RetStatus": 9, "StrRetStatus": "AllowSend"}
    assert sms_gateway._payamak_rest_send_sms_response_ok(payload) is True
