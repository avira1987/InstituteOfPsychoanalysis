"""HTTP-level tests for AlocomClient with mocked pnlapi (respx)."""

import pytest
import respx

from app.services.alocom_client import AlocomClient, AlocomAPIError


@pytest.fixture
def alocom_settings(monkeypatch):
    class S:
        ALOCOM_API_BASE = "https://pnlapi.test"
        ALOCOM_USERNAME = "agent_u"
        ALOCOM_PASSWORD = "agent_p"
        ALOCOM_PATH_LOGIN = "/api/v1/auth/login"
        ALOCOM_PATH_CREATE_EVENT = "/api/v1/agent/event/store"
        ALOCOM_PATH_REGISTER_IN_EVENT = "/api/v1/agent/event/{event_id}/register-user"
        ALOCOM_PATH_CREATE_USER = "/api/v1/agent/users/store"

    monkeypatch.setattr("app.services.alocom_client.get_settings", lambda: S())


@pytest.mark.asyncio
@respx.mock
async def test_login_and_create_event(alocom_settings):
    respx.post("https://pnlapi.test/api/v1/auth/login").mock(
        return_value=respx.MockResponse(200, json={"data": {"token": "tok_test_1"}})
    )
    respx.post("https://pnlapi.test/api/v1/agent/event/store").mock(
        return_value=respx.MockResponse(
            200,
            json={
                "data": {
                    "event": {
                        "id": 77,
                        "alocom_link": "https://class.test/room/abc",
                    }
                }
            },
        )
    )

    client = AlocomClient()
    out = await client.create_event(
        title="Test class",
        agent_service_id=10,
        slug="slug-test-1",
        start_by_admin=1,
        status=1,
        duration_time=60,
    )
    assert out["data"]["event"]["id"] == 77


@pytest.mark.asyncio
@respx.mock
async def test_login_failure_raises(alocom_settings):
    respx.post("https://pnlapi.test/api/v1/auth/login").mock(return_value=respx.MockResponse(401, json={}))

    client = AlocomClient()
    with pytest.raises(AlocomAPIError) as ei:
        await client.create_event(
            title="x",
            agent_service_id=1,
            slug="s",
        )
    assert ei.value.status_code == 401
