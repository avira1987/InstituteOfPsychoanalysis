"""HTTP tests for request-id headers, 500 error_id, and skipped health access logs."""

from __future__ import annotations

import logging

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.observability.ring_buffer import reset_for_tests


@pytest.fixture
def client():
    reset_for_tests()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c


def test_health_sets_request_id_header(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    rid = r.headers.get("x-request-id")
    assert rid
    assert len(rid) >= 8


def test_client_request_id_is_echoed(client: TestClient):
    r = client.get("/health", headers={"X-Request-ID": "client-rid-12345"})
    assert r.headers.get("x-request-id") == "client-rid-12345"


def test_health_is_not_access_logged(client: TestClient, caplog: pytest.LogCaptureFixture):
    caplog.set_level(logging.INFO, logger="app.observability.access")
    client.get("/health")
    access = [rec for rec in caplog.records if rec.name == "app.observability.access"]
    assert not any(getattr(rec, "path", "") in ("/health", "/health/ready") for rec in access)


def test_observability_boom_returns_error_id(client: TestClient):
    r = client.get("/debug/observability-boom")
    assert r.status_code == 500
    body = r.json()
    assert body.get("error_id")
    assert r.headers.get("x-request-id")
    assert body["error_id"] == r.headers.get("x-request-id")


def test_observability_endpoint_requires_auth(client: TestClient):
    r = client.get("/api/admin/system/observability")
    assert r.status_code in (401, 403)
