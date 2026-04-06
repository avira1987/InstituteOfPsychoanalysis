"""
E2E مرورگر: SPA روی همان بک‌اند (مسیر /anistito مطابق build Vite).

پیش‌نیاز: pip install playwright && playwright install chromium
و: npm run build در admin-ui
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def _parse_challenge_answer(question: str) -> str | None:
    for pat in (
        r"حاصل\s*(\d+)\s*\+\s*(\d+)",
        r"(\d+)\s*\+\s*(\d+)",
    ):
        m = re.search(pat, question)
        if m:
            return str(int(m.group(1)) + int(m.group(2)))
    return None


def test_e2e_homepage_loads(playwright_page, e2e_server_url: str):
    """صفحهٔ اصلی SPA بدون خطا لود می‌شود."""
    page = playwright_page
    page.goto(f"{e2e_server_url}/anistito/")
    expect(page).to_have_title(re.compile(r"روانکاوی|Psychoanalysis", re.I))


def test_e2e_admin_password_login_reaches_panel(playwright_page, e2e_server_url: str):
    """ورود با رمز عبور (چالش عددی) و رسیدن به مسیر پنل."""
    page = playwright_page
    page.goto(f"{e2e_server_url}/anistito/login")

    page.get_by_role("button", name="ورود با رمز عبور").click()
    page.wait_for_selector('input[placeholder*="نام کاربری"]', timeout=30_000)

    page.locator('input[placeholder*="نام کاربری"]').fill("admin")
    page.locator('input[type="password"]').fill("admin123")

    page.wait_for_selector("text=کد امنیتی", timeout=30_000)
    # متن سوال داخل بلوک «کد امنیتی» (نه کل کارت که لینک‌ها و تب‌ها را هم دارد)
    row = page.locator(".form-group").filter(has_text=re.compile("کد امنیتی"))
    qt = row.locator("div").filter(has_text=re.compile(r"\+")).first.inner_text(timeout=10_000)
    ans = _parse_challenge_answer(qt)
    assert ans is not None, f"سوال چالش پارس نشد: {qt!r}"
    page.get_by_placeholder("پاسخ کد امنیتی را وارد کنید").fill(ans)

    page.locator(".login-card").locator('button[type="submit"]').click()

    expect(page).to_have_url(re.compile(r".*/panel.*"), timeout=30_000)
