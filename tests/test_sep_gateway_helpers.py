from types import SimpleNamespace

from starlette.testclient import TestClient

from app.api.payment_routes import _should_try_sep_after_zibal
from app.main import app
from app.services.payment_gateway import (
    PaymentRequest,
    _sep_token_payload,
    normalize_sep_cell_number,
    sep_pay_get_url,
)


def test_normalize_sep_cell_number():
    assert normalize_sep_cell_number("09121234567") == "9121234567"
    assert normalize_sep_cell_number("9121234567") == "9121234567"
    assert normalize_sep_cell_number("+989121234567") == "9121234567"
    assert normalize_sep_cell_number("") == ""
    assert normalize_sep_cell_number("123") == ""


def test_sep_token_payload_omits_empty_cell_and_password():
    req = PaymentRequest(
        amount=150000,
        description="t",
        callback_url="https://lms.example.ir/anistito/api/payment/callback",
        reference_id="abc123def4567890",
        mobile="",
    )
    payload = _sep_token_payload(req, "12345678")
    assert payload["action"] == "token"
    assert payload["TerminalId"] == "12345678"
    assert payload["Amount"] == 150000
    assert payload["ResNum"] == "abc123def4567890"
    assert payload["RedirectUrl"].startswith("https://")
    assert "CellNumber" not in payload
    assert "Password" not in payload


def test_sep_pay_get_url_uses_official_sendtoken():
    url = sep_pay_get_url("abc123")
    assert url == "https://sep.shaparak.ir/OnlinePG/SendToken?token=abc123"
    from app.services.payment_gateway import sep_browser_start_url

    assert sep_browser_start_url("tok+/=x") == sep_pay_get_url("tok+/=x")
    assert "SendToken?token=" in sep_browser_start_url("tok+/=x")
    assert "sep/start" not in sep_browser_start_url("abc")


def test_sep_start_posts_token_form():
    with TestClient(app) as client:
        r = client.get("/api/payment/sep/start", params={"token": "tokentest1"}, follow_redirects=False)
        assert r.status_code == 302
        loc = r.headers.get("location") or ""
        assert loc.startswith("https://sep.shaparak.ir/OnlinePG/SendToken?token=")
        assert "tokentest1" in loc
        bad = client.get("/api/payment/sep/start", params={"token": ""}, follow_redirects=False)
        assert bad.status_code == 400


def test_should_try_sep_after_zibal():
    ready = SimpleNamespace(PAYMENT_ZIBAL_ONLY=False, SEP_TERMINAL_ID="12345678")
    assert _should_try_sep_after_zibal("zibal", ready) is True
    assert _should_try_sep_after_zibal("saman", ready) is False
    assert _should_try_sep_after_zibal("zarinpal", ready) is False
    blocked = SimpleNamespace(PAYMENT_ZIBAL_ONLY=True, SEP_TERMINAL_ID="12345678")
    assert _should_try_sep_after_zibal("zibal", blocked) is False
    missing = SimpleNamespace(PAYMENT_ZIBAL_ONLY=False, SEP_TERMINAL_ID="")
    assert _should_try_sep_after_zibal("zibal", missing) is False
