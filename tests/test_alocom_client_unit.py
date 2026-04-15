"""Unit tests for Alocom client helpers (no database)."""

from app.services.alocom_client import _extract_event_id_and_link, _extract_token


def test_extract_token_flat():
    assert _extract_token({"token": "abc"}) == "abc"
    assert _extract_token({"access_token": "at"}) == "at"


def test_extract_token_nested():
    assert _extract_token({"data": {"token": "nested"}}) == "nested"
    assert _extract_token({"data": {"accessToken": "camel"}}) == "camel"


def test_extract_event_id_and_link():
    eid, link = _extract_event_id_and_link(
        {"data": {"event": {"id": 54, "alocom_link": "https://class.example/x"}}}
    )
    assert eid == "54"
    assert link == "https://class.example/x"
