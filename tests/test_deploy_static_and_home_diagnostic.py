"""
تشخیص منبع مشکل «بعد از build تغییرات دیده نمی‌شود»:

۱) مسیر واقعی سرو فرانت همان admin-ui/dist کنار ریشه پروژه است (نه جای دیگر).
۲) اگر dist وجود نداشته باشد، روت / JSON «build نشده» برمی‌گرداند — نه SPA.
۳) اگر dist باشد، index.html باید به /assets/ اشاره کند و همان فایل JS قابل دریافت باشد.
۴) endpoint /api/auth/home در کد ثبت شده و برای ادمین redirect_url=/panel برمی‌گرداند.

این تست‌ها محیط اجرای uvicorn روی پورت ۸۰۰۰ را عوض نمی‌کنند؛ اگر اینجا پاس شوند ولی
مرورگر تغییر نمی‌بیند، منبع مشکل خارج از کد است: پروسه دیگری روی پورت، کش مرورگر،
یا اجرای سرور از پوشهٔ دیگر.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


def test_admin_ui_dir_is_project_root_admin_ui_dist():
    """مسیر سرو استاتیک = ریشه_پروژه/admin-ui/dist (همان جایی که npm run build می‌نویسد)."""
    import app.main as main_mod

    repo_root = Path(main_mod.__file__).resolve().parent.parent
    expected = repo_root / "admin-ui" / "dist"
    assert main_mod.ADMIN_UI_DIR.resolve() == expected.resolve(), (
        f"کد انتظار دارد SPA از {expected} سرو شود؛ "
        f"اگر uvicorn از cwd دیگری اجرا شود __file__ همچنان درست است — "
        f"اما اگر پروژه کپی شده باشد، build باید همان کپی را به‌روز کند."
    )


def test_dist_state_diagnostic_message():
    """
    وضعیت dist را گزارش می‌کند: بدون dist، پورت 8000 هرگز SPA جدید نشان نمی‌دهد.
    """
    import app.main as main_mod

    dist = main_mod.ADMIN_UI_DIR.resolve()
    if not dist.is_dir():
        pytest.fail(
            f"پوشه dist وجود ندارد: {dist}\n"
            "منبع مشکل: هیچ بیلدی برای مسیری که FastAPI می‌خواند وجود نیست.\n"
            "کار: در همان ریشه پروژه: cd admin-ui && npm run build"
        )

    index = dist / "index.html"
    if not index.is_file():
        pytest.fail(
            f"dist بدون index.html است: {dist}\n"
            "منبع مشکل: بیلد ناقص یا پاک شده.\n"
            "کار: npm run build را دوباره اجرا کنید."
        )

    html = index.read_text(encoding="utf-8", errors="replace")
    # Vite: /assets/index-xxxxx.js
    scripts = re.findall(r'src="(/assets/[^"]+\.js)"', html)
    if not scripts:
        pytest.fail(
            "index.html هیچ script با مسیر /assets/*.js ندارد؛ بیلد Vite معمولی نیست.\n"
            "منبع مشکل: فایل index اشتباه یا بیلد خراب."
        )

    main_js = dist / "assets" / Path(scripts[0]).name
    if not main_js.is_file():
        pytest.fail(
            f"index.html به {scripts[0]} اشاره می‌کند اما فایل روی دیسک نیست: {main_js}\n"
            "منبع مشکل: بیلد ناقص یا sync ناقص به سرور.\n"
            "کار: npm run build و مطمئن شوید کل پوشه dist کپی می‌شود."
        )


@pytest.mark.asyncio
async def test_root_returns_spa_html_when_dist_exists():
    """وقتی dist هست، GET / باید HTML باشد نه JSON «build نشده»."""
    import app.main as main_mod
    from app.main import app

    if not main_mod.ADMIN_UI_DIR.exists():
        pytest.skip("بدون dist این تست معنا ندارد")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/")

    assert r.status_code == 200, r.text
    ctype = (r.headers.get("content-type") or "").lower()
    assert "text/html" in ctype, (
        f"انتظار HTML برای /؛ گرفت: content-type={ctype!r}\n"
        "اگر JSON است، یعنی در زمان import اپ، dist وجود نداشته و مسیر SPA mount نشده.\n"
        "منبع مشکل: سرور از ریشهٔ دیگری import می‌کند یا dist قبل از استارت ساخته نشده."
    )
    assert "/assets/" in r.text, "index سرو‌شده باید به /assets/ ارجاع دهد"


@pytest.mark.asyncio
async def test_asset_from_index_is_reachable():
    """همان bundle اصلی که index لود می‌کند باید از /assets/ با اپ قابل GET باشد."""
    import app.main as main_mod
    from app.main import app

    if not main_mod.ADMIN_UI_DIR.exists():
        pytest.skip("بدون dist")

    index_html = (main_mod.ADMIN_UI_DIR / "index.html").read_text(encoding="utf-8", errors="replace")
    m = re.search(r'src="(/assets/[^"]+\.js)"', index_html)
    if not m:
        pytest.fail("نمی‌توان مسیر JS را از index استخراج کرد")
    path = m.group(1)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get(path)

    assert r.status_code == 200, (
        f"GET {path} → {r.status_code}\n"
        "منبع مشکل: mount /assets با پوشه dist هم‌خوان نیست یا فایل bundle حذف شده."
    )
    assert len(r.content) > 100, "bundle خالی یا خیلی کوچک است"


@pytest.mark.asyncio
async def test_api_auth_home_exists_and_shape_for_admin():
    """
    /api/auth/home باید ۲۰۰ و فیلدهای لازم را بدهد (بدون نیاز به DB برای نقش ادمین).
    اگر این تست در محیط شما fail شود، مرورگر هرگز از login به مسیر جدید نمی‌رود
    (یا بک‌اند قدیمی است).
    """
    import uuid

    from app.database import get_db
    from app.main import app
    from app.api.auth import get_current_user
    from app.models.operational_models import User

    admin = User(
        id=uuid.uuid4(),
        username="diag_admin",
        email=None,
        hashed_password="x",
        role="admin",
        is_active=True,
    )

    async def override_user():
        return admin

    async def override_db():
        class _Dummy:
            pass

        yield _Dummy()

    app.dependency_overrides[get_current_user] = override_user
    app.dependency_overrides[get_db] = override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get("/api/auth/home")
    finally:
        app.dependency_overrides.clear()

    assert r.status_code == 200, (
        f"/api/auth/home → {r.status_code} {r.text}\n"
        "منبع مشکل: route ثبت نشده یا بک‌اند قدیمی بدون این endpoint در حال اجراست.\n"
        "کار: uvicorn را ری‌استارت کنید و مطمئن شوید همان کد همین repo اجرا می‌شود."
    )
    data = r.json()
    assert "redirect_url" in data, data
    assert data["redirect_url"] == "/panel"
    assert "primary_instance_id" in data


@pytest.mark.asyncio
async def test_api_auth_home_requires_auth_without_override():
    """بدون توکن نباید ۲۰۰ بدهد — اگر ۲۰۰ داد یعنی امنیت/مسیر اشتباه است."""
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/auth/home")

    assert r.status_code == 401, (
        f"بدون Authorization انتظار 401؛ گرفت {r.status_code}\n"
        f"body={r.text[:500]}"
    )
