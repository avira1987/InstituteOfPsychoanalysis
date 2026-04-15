#!/usr/bin/env python3
"""تست دستی ملی‌پیامک — چند مسیر ارسال را پشت‌سرهم امتحان می‌کند.

اجرا از هر مسیر (اسکریپت خودش به روت پروژه می‌رود):

  python scripts/manual_test_mellipayamak_sms.py
  python scripts/manual_test_mellipayamak_sms.py --phone 09112732986
  python scripts/manual_test_mellipayamak_sms.py --stop-on-first-success
  python scripts/manual_test_mellipayamak_sms.py --dry-run
  python scripts/manual_test_mellipayamak_sms.py --only rest_apikey_as_password

شماره گیرنده: MANUAL_SMS_TEST_CONFIG['SMS_TEST_PHONE'] یا متغیر SMS_TEST_PHONE یا --phone.

هشدار: به‌طور پیش‌فرض برای هر سناریوی «قابل اجرا» یک پیامک واقعی به همان شماره می‌رود.
کد خروج 0 اگر حداقل یک ارسال موفق باشد، وگرن 1.

مقادیر حساس را می‌توانید در همین فایل، در MANUAL_SMS_TEST_CONFIG بگذارید (هر فیلد خالی = همان مقدار از .env).
این فایل را با رمز/API واقعی commit نکنید.

اگر پاسخ API «موفق» است اما پیام به گوشی نمی‌رسد: تأخیر اپراتور، فیلتر/بلک‌لیست، یا گزارش تحویل را
در پنل ملی‌پیامک بررسی کنید؛ پاسخ AllowSend فقط پذیرش درخواست است نه رسیدن قطعی.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import os
import sys
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Awaitable, Callable

ROOT = Path(__file__).resolve().parent.parent

# =============================================================================
# پیکربندی تست ملی‌پیامک — اینجا user/pass/API/خط/شماره را قرار دهید.
# هر مقدار خالی ("") یعنی از فایل .env در روت پروژه خوانده می‌شود.
# =============================================================================
MANUAL_SMS_TEST_CONFIG: dict[str, str] = {
    # نام کاربری پنل ملی‌پیامک (مثال پروژه؛ می‌توانید خالی بگذارید تا از .env بیاید)
    "SMS_USERNAME": "9032054361",
    "SMS_PASSWORD": "",
    "SMS_API_KEY": "",
    "SMS_LINE_NUMBER": "",
    # شماره گیرنده تست (۱۱ رقم با ۰۹…)
    "SMS_TEST_PHONE": "09112732986",
}

_SMS_KEYS_FROM_FILE = (
    "SMS_USERNAME",
    "SMS_PASSWORD",
    "SMS_API_KEY",
    "SMS_LINE_NUMBER",
)


def _apply_manual_sms_config_to_environ() -> list[str]:
    """مقادیر غیرخالی را روی os.environ می‌گذارد (اولویت بالاتر از .env برای pydantic)."""
    applied: list[str] = []
    for key in _SMS_KEYS_FROM_FILE:
        raw = MANUAL_SMS_TEST_CONFIG.get(key)
        if raw is None:
            continue
        v = str(raw).strip()
        if v:
            os.environ[key] = v
            applied.append(key)
    return applied


def _default_test_phone() -> str:
    p = (MANUAL_SMS_TEST_CONFIG.get("SMS_TEST_PHONE") or "").strip()
    if p:
        return p
    return os.environ.get("SMS_TEST_PHONE", "09112732986")

_MISSING = object()

ScenarioMaker = Callable[[], Callable[[], Awaitable[dict[str, Any]]]]


def _configure_stdio_utf8() -> None:
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _mask_secret(s: str, keep: int = 4) -> str:
    t = (s or "").strip()
    if len(t) <= keep:
        return "***" if t else "(خالی)"
    return f"…{t[-keep:]}"


@contextmanager
def _env_overlay(updates: dict[str, str | None]):
    """موقت: مقدار None یعنی حذف کلید از os.environ."""
    backup: dict[str, Any] = {}
    try:
        for k, v in updates.items():
            backup[k] = os.environ.get(k, _MISSING)
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, old in backup.items():
            if old is _MISSING:
                os.environ.pop(k, None)
            else:
                os.environ[k] = old


def _reload_sms_gateway():
    from app.config import get_settings

    get_settings.cache_clear()
    import app.services.sms_gateway as sg

    importlib.reload(sg)
    return sg


async def _run_scenario(
    name_fa: str,
    name_en: str,
    coro: Callable[[], Awaitable[dict[str, Any]]],
    *,
    dry_run: bool,
) -> dict[str, Any]:
    print("\n" + "=" * 60)
    print(f"سناریو: {name_fa}  ({name_en})")
    print("=" * 60)
    if dry_run:
        print("(dry-run — ارسال انجام نشد)")
        return {"success": False, "skipped": True, "dry_run": True}

    result = await coro()
    ok = bool(result.get("success"))
    print("نتیجه:", "موفق" if ok else "ناموفق")
    print("جزئیات:", result)
    return result


def main() -> int:
    _configure_stdio_utf8()
    os.chdir(ROOT)
    sys.path.insert(0, str(ROOT))

    parser = argparse.ArgumentParser(description="تست دستی ارسال پیامک ملی‌پیامک (چند مسیر)")
    parser.add_argument(
        "--phone",
        default=_default_test_phone(),
        help="شماره گیرنده (پیش‌فرض: MANUAL_SMS_TEST_CONFIG یا env SMS_TEST_PHONE یا 09112732986)",
    )
    parser.add_argument(
        "--otp-code",
        default="123456",
        help="کد عددی برای تست SendOtp (فقط ارقام لاتین)",
    )
    parser.add_argument(
        "--stop-on-first-success",
        action="store_true",
        help="بعد از اولین ارسال موفق متوقف شو",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="فقط سناریوها را چاپ کن؛ هیچ درخواست HTTP ارسال نشود",
    )
    parser.add_argument(
        "--no-force-provider",
        action="store_true",
        help="SMS_PROVIDER را اجباراً mellipayamak نکن (همان .env)",
    )
    parser.add_argument(
        "--ignore-file-config",
        action="store_true",
        help="MANUAL_SMS_TEST_CONFIG را اعمال نکن (فقط .env و آرگومان‌ها)",
    )
    parser.add_argument(
        "--only",
        metavar="NAME",
        default="",
        help=(
            "فقط یک سناریو (نام انگلیسی): send_sms | send_otp_sms | rest_SendSMS | rest_SendOtp | "
            "console_only | rest_password_only | rest_apikey_as_password"
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )

    applied_from_file: list[str] = []
    if not args.ignore_file_config:
        applied_from_file = _apply_manual_sms_config_to_environ()

    if not args.no_force_provider:
        os.environ["SMS_PROVIDER"] = "mellipayamak"

    from app.config import get_settings

    get_settings.cache_clear()
    base = get_settings()

    phone = args.phone.strip()
    print("شماره تست:", phone)
    if applied_from_file:
        print("اعمال‌شده از همین فایل (MANUAL_SMS_TEST_CONFIG):", ", ".join(applied_from_file))
    else:
        print("پیکربندی SMS از .env / محیط (بدون مقدار غیرخالی در فایل تست)")
    print("خط ارسال (مؤثر):", _mask_secret(base.SMS_LINE_NUMBER, 6))
    print("SMS_USERNAME:", _mask_secret(base.SMS_USERNAME, 3))
    print("SMS_PASSWORD:", _mask_secret(base.SMS_PASSWORD, 2))
    print("SMS_API_KEY:", _mask_secret(base.SMS_API_KEY, 4))
    print("SMS_PROVIDER (پس از اجبار اسکریپت):", base.SMS_PROVIDER)

    ts = int(time.time())
    body_sms = f"Anistito manual [{ts}]"
    otp_code = "".join(c for c in args.otp_code if c.isdigit()) or "123456"

    scenarios: list[tuple[str, str, ScenarioMaker]] = []

    def mk1() -> Callable[[], Awaitable[dict[str, Any]]]:
        sg = _reload_sms_gateway()

        async def run():
            return await sg.send_sms(phone, body_sms + " send_sms")

        return run

    scenarios.append(("ارسال متنی (send_sms طبق پیکربندی)", "send_sms", mk1))

    def mk2() -> Callable[[], Awaitable[dict[str, Any]]]:
        sg = _reload_sms_gateway()

        async def run():
            return await sg.send_otp_sms(phone, otp_code)

        return run

    scenarios.append(("ورود OTP (send_otp_sms)", "send_otp_sms", mk2))

    def mk3() -> Callable[[], Awaitable[dict[str, Any]]]:
        sg = _reload_sms_gateway()
        u = (sg.settings.SMS_USERNAME or "").strip()
        pw = sg._mellipayamak_password_for_rest()  # noqa: SLF001

        async def run():
            if not u or not pw:
                return {
                    "success": False,
                    "skipped": True,
                    "reason": "SMS_USERNAME یا password/APIKey برای REST ناقص است",
                }
            return await sg._send_mellipayamak_rest_classic(phone, body_sms + " REST SendSMS")  # noqa: SLF001

        return run

    scenarios.append(("REST مستقیم SendSMS", "rest_SendSMS", mk3))

    def mk4() -> Callable[[], Awaitable[dict[str, Any]]]:
        sg = _reload_sms_gateway()
        u = (sg.settings.SMS_USERNAME or "").strip()
        pw = sg._mellipayamak_password_for_rest()  # noqa: SLF001

        async def run():
            if not u or not pw:
                return {
                    "success": False,
                    "skipped": True,
                    "reason": "SMS_USERNAME یا password/APIKey برای REST ناقص است",
                }
            return await sg._send_mellipayamak_otp_rest(phone, otp_code, u, pw)  # noqa: SLF001

        return run

    scenarios.append(("REST مستقیم SendOtp", "rest_SendOtp", mk4))

    def mk5() -> Callable[[], Awaitable[dict[str, Any]]]:
        async def run():
            with _env_overlay({"SMS_USERNAME": ""}):
                sg = _reload_sms_gateway()
                return await sg._send_mellipayamak(phone, body_sms + " console")  # noqa: SLF001

        return run

    scenarios.append(("فقط API کنسول (send/simple، بدون username)", "console_only", mk5))

    def mk6() -> Callable[[], Awaitable[dict[str, Any]]]:
        pw0 = (base.SMS_PASSWORD or "").strip()
        if not pw0:

            async def run():
                return {
                    "success": False,
                    "skipped": True,
                    "reason": "SMS_PASSWORD در .env خالی است",
                }

            return run

        async def run():
            with _env_overlay({"SMS_API_KEY": ""}):
                sg = _reload_sms_gateway()
                u = (sg.settings.SMS_USERNAME or "").strip()
                pwx = sg._mellipayamak_password_for_rest()  # noqa: SLF001
                if not u or not pwx:
                    return {
                        "success": False,
                        "skipped": True,
                        "reason": "با خالی کردن SMS_API_KEY دیگر passwordای برای REST نیست یا username نیست",
                    }
                return await sg._send_mellipayamak_rest_classic(phone, body_sms + " REST pwd-only")  # noqa: SLF001

        return run

    scenarios.append(("REST با SMS_PASSWORD (SMS_API_KEY موقت خالی)", "rest_password_only", mk6))

    def mk7() -> Callable[[], Awaitable[dict[str, Any]]]:
        ak = (base.SMS_API_KEY or "").strip()
        u0 = (base.SMS_USERNAME or "").strip()
        if not ak or not u0:

            async def run():
                return {
                    "success": False,
                    "skipped": True,
                    "reason": "برای این تست SMS_USERNAME و SMS_API_KEY هر دو لازم است",
                }

            return run

        async def run():
            with _env_overlay({"SMS_PASSWORD": ""}):
                sg = _reload_sms_gateway()
                u = (sg.settings.SMS_USERNAME or "").strip()
                pw = sg._mellipayamak_password_for_rest()  # noqa: SLF001
                if not u or not pw:
                    return {
                        "success": False,
                        "skipped": True,
                        "reason": "بعد از خالی کردن SMS_PASSWORD، APIKey هم خالی است",
                    }
                return await sg._send_mellipayamak_rest_classic(phone, body_sms + " REST apikey-pw")  # noqa: SLF001

        return run

    scenarios.append(("REST با APIKey به‌جای password (SMS_PASSWORD خالی)", "rest_apikey_as_password", mk7))

    only = (args.only or "").strip()
    if only:
        scenarios = [s for s in scenarios if s[1] == only]
        if not scenarios:
            allowed = (
                "send_sms, send_otp_sms, rest_SendSMS, rest_SendOtp, "
                "console_only, rest_password_only, rest_apikey_as_password"
            )
            print("نام سناریوی نامعتبر:", only)
            print("مقادیر مجاز --only:", allowed)
            return 2

    async def run_all():
        any_success = False
        for name_fa, name_en, maker in scenarios:

            async def one_scenario(m=maker):
                run_fn = m()
                return await run_fn()

            res = await _run_scenario(name_fa, name_en, one_scenario, dry_run=args.dry_run)
            if res.get("skipped") and not args.dry_run:
                print("رد شد:", res.get("reason", res))
            if res.get("success"):
                any_success = True
                if args.stop_on_first_success:
                    print("\n*** توقف: اولین ارسال موفق ***")
                    break
        return any_success

    ok = asyncio.run(run_all())
    print("\n" + "=" * 60)
    if args.dry_run:
        print("پایان (dry-run).")
        return 0
    print("حداقل یک ارسال موفق:", "بله" if ok else "خیر")
    print("=" * 60)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
