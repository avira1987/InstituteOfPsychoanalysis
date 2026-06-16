"""
Tests for website availability: API health, SPA root, static assets, and API routes.

These tests help catch when the site is not accessible (e.g. missing dist,
wrong base path, or routes overridden).
"""

import pytest
from pathlib import Path
from starlette.testclient import TestClient

from app.main import app

# Path used by main.py to serve Admin UI (must match main.py)
ADMIN_UI_DIR = Path(__file__).resolve().parent.parent / "admin-ui" / "dist"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health_endpoint_returns_200(client: TestClient):
    """Health endpoint must always be available."""
    r = client.get("/health")
    assert r.status_code == 200, f"Health check failed: {r.status_code} {r.text}"
    assert r.json().get("status") == "healthy"


def test_root_returns_200(client: TestClient):
    """Root URL must return 200 (SPA HTML or API JSON when dist missing)."""
    r = client.get("/")
    assert r.status_code == 200, f"Root failed: {r.status_code} {r.text}"


def test_root_when_dist_exists_returns_html_with_correct_asset_paths(client: TestClient):
    """
    When admin-ui/dist exists, GET / must return HTML and asset URLs reference /assets/
    (بیلد production ممکن است /anistito/assets/ باشد؛ بک‌اند هر دو را سرو می‌کند).
    """
    if not ADMIN_UI_DIR.exists():
        pytest.skip("admin-ui/dist not found — run 'npm run build' in admin-ui/")
    r = client.get("/")
    assert r.status_code == 200
    content_type = r.headers.get("content-type", "")
    assert "text/html" in content_type, f"Expected HTML, got {content_type}"
    html = r.text
    assert "/assets/" in html, "HTML باید به bundle تحت /assets/ (یا /anistito/assets/) اشاره کند"
    assert "<div id=\"root\"></div>" in html or 'id="root"' in html, "SPA root div missing"


def test_root_when_dist_missing_returns_json(client: TestClient):
    """When admin-ui/dist does not exist, root should return JSON with instructions."""
    if ADMIN_UI_DIR.exists():
        pytest.skip("admin-ui/dist exists — this test is for missing dist")
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "name" in data
    assert "note" in data or "docs" in data


def test_assets_accessible_when_dist_exists(client: TestClient):
    """When dist exists, /assets/* must be served so the SPA loads."""
    if not ADMIN_UI_DIR.exists():
        pytest.skip("admin-ui/dist not found")
    assets_dir = ADMIN_UI_DIR / "assets"
    if not assets_dir.is_dir():
        pytest.skip("admin-ui/dist/assets not found")
    js_files = list(assets_dir.glob("*.js"))
    if not js_files:
        pytest.skip("No JS assets in dist/assets")
    asset_name = js_files[0].name
    r = client.get(f"/assets/{asset_name}")
    assert r.status_code == 200, f"Asset /assets/{asset_name} failed: {r.status_code}"


def test_api_auth_login_not_overridden(client: TestClient):
    """API routes must not be overridden by SPA catch-all (e.g. /api -> index.html)."""
    r = client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
    content_type = r.headers.get("content-type", "")
    assert "application/json" in content_type, (
        f"Expected JSON from /api/auth/login, got {content_type} — API may be overridden"
    )
    assert r.status_code in (200, 401), f"Unexpected status: {r.status_code} {r.text}"


def test_get_api_returns_404_json_not_html(client: TestClient):
    """GET /api (no subpath) must return 404 JSON, not SPA HTML."""
    r = client.get("/api")
    assert r.status_code == 404
    assert "application/json" in r.headers.get("content-type", "")
    assert "detail" in r.json()


def test_spa_client_routes_serve_index_html(client: TestClient):
    """Client-side routes like /login or /panel should get index.html for SPA routing."""
    if not ADMIN_UI_DIR.exists():
        pytest.skip("admin-ui/dist not found")
    for path in ["/login", "/panel", "/panel/processes"]:
        r = client.get(path)
        assert r.status_code == 200, f"SPA route {path} failed: {r.status_code}"
        assert "text/html" in r.headers.get("content-type", "")
        assert 'id="root"' in r.text or "<div id=\"root\"></div>" in r.text
