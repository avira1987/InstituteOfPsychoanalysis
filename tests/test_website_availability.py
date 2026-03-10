"""
Tests for website availability: API health, SPA root, static assets, and API routes.

These tests help catch when the site is not accessible (e.g. missing dist,
wrong base path, or routes overridden).
"""

import re
import pytest
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from app.main import app

# Path used by main.py to serve Admin UI (must match main.py)
ADMIN_UI_DIR = Path(__file__).resolve().parent.parent / "admin-ui" / "dist"


@pytest.mark.asyncio
async def test_health_endpoint_returns_200():
    """Health endpoint must always be available."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/health")
        assert r.status_code == 200, f"Health check failed: {r.status_code} {r.text}"
        assert r.json().get("status") == "healthy"


@pytest.mark.asyncio
async def test_root_returns_200():
    """Root URL must return 200 (SPA HTML or API JSON when dist missing)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
        assert r.status_code == 200, f"Root failed: {r.status_code} {r.text}"


@pytest.mark.asyncio
async def test_root_when_dist_exists_returns_html_with_correct_asset_paths():
    """
    When admin-ui/dist exists, GET / must return HTML and asset URLs must be
    under /assets/ (not /anistito/assets/) so the page loads in browser.
    """
    if not ADMIN_UI_DIR.exists():
        pytest.skip("admin-ui/dist not found — run 'npm run build' in admin-ui/")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        assert "text/html" in content_type, f"Expected HTML, got {content_type}"
        html = r.text
        # Script and link must point to /assets/ so they load; /anistito/assets/ would 404 on port 3000
        assert '/assets/' in html, "HTML should reference /assets/ for JS/CSS"
        assert '/anistito/assets/' not in html, (
            "HTML must not reference /anistito/assets/ when base is / — causes white screen"
        )
        assert "<div id=\"root\"></div>" in html or 'id="root"' in html, "SPA root div missing"


@pytest.mark.asyncio
async def test_root_when_dist_missing_returns_json():
    """When admin-ui/dist does not exist, root should return JSON with instructions."""
    if ADMIN_UI_DIR.exists():
        pytest.skip("admin-ui/dist exists — this test is for missing dist")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")
        assert r.status_code == 200
        data = r.json()
        assert "name" in data
        assert "note" in data or "docs" in data


@pytest.mark.asyncio
async def test_assets_accessible_when_dist_exists():
    """When dist exists, /assets/* must be served so the SPA loads."""
    if not ADMIN_UI_DIR.exists():
        pytest.skip("admin-ui/dist not found")
    assets_dir = ADMIN_UI_DIR / "assets"
    if not assets_dir.is_dir():
        pytest.skip("admin-ui/dist/assets not found")
    # Use first JS file (main bundle) as representative
    js_files = list(assets_dir.glob("*.js"))
    if not js_files:
        pytest.skip("No JS assets in dist/assets")
    asset_name = js_files[0].name
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(f"/assets/{asset_name}")
        assert r.status_code == 200, f"Asset /assets/{asset_name} failed: {r.status_code}"


@pytest.mark.asyncio
async def test_api_auth_login_not_overridden():
    """API routes must not be overridden by SPA catch-all (e.g. /api -> index.html)."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post("/api/auth/login", data={"username": "admin", "password": "admin123"})
        # Must be JSON response (200 with token or 401), not HTML
        content_type = r.headers.get("content-type", "")
        assert "application/json" in content_type, (
            f"Expected JSON from /api/auth/login, got {content_type} — API may be overridden"
        )
        assert r.status_code in (200, 401), f"Unexpected status: {r.status_code} {r.text}"


@pytest.mark.asyncio
async def test_get_api_returns_404_json_not_html():
    """GET /api (no subpath) must return 404 JSON, not SPA HTML."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api")
        assert r.status_code == 404
        assert "application/json" in r.headers.get("content-type", "")
        assert "detail" in r.json()


@pytest.mark.asyncio
async def test_spa_client_routes_serve_index_html():
    """Client-side routes like /login or /panel should get index.html for SPA routing."""
    if not ADMIN_UI_DIR.exists():
        pytest.skip("admin-ui/dist not found")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for path in ["/login", "/panel", "/panel/processes"]:
            r = await client.get(path)
            assert r.status_code == 200, f"SPA route {path} failed: {r.status_code}"
            assert "text/html" in r.headers.get("content-type", "")
            assert 'id="root"' in r.text or "<div id=\"root\"></div>" in r.text
