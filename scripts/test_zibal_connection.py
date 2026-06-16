#!/usr/bin/env python3
"""
تست اتصال به درگاه زیبال (همان منطق app) — خروجی را کپی کنید و بفرستید.

اجرا از ریشهٔ مخزن:
  python scripts/test_zibal_connection.py

ذخیرهٔ خروجی در فایل (برای ارسال):
  python scripts/test_zibal_connection.py > zibal_test_log.txt 2>&1

در ویندوز اگر کاراکترهای فارسی در Notepad درست نیست:
  chcp 65001
  set PYTHONUTF8=1
  python scripts/test_zibal_connection.py > zibal_test_log.txt 2>&1
"""
from __future__ import annotations

import asyncio
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

# روت پروژه در path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def _configure_stdio_utf8() -> None:
    """ریدایرکت `> file` روی ویندوز اغلب cp1252 است؛ برای فارسی UTF-8 لازم است."""
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError, AttributeError):
                pass


def _safe_repr(text: str) -> str:
    try:
        return repr(text)
    except Exception:
        return ascii(text)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _mask(s: str, show: int = 8) -> str:
    if not s:
        return "(empty)"
    s = str(s).strip()
    if len(s) <= show:
        return s[:3] + "..." if len(s) > 3 else s
    return f"{s[:show]}... (len={len(s)})"


def _print_section(title: str) -> None:
    print()
    print("=" * 60)
    print(title)
    print("=" * 60)


async def main() -> int:
    _print_section("anistito - Zibal connectivity test")
    print(f"time_utc: {_utc_now()}")
    print(f"python: {sys.version.split()[0]}")

    try:
        from app.config import get_settings, effective_payment_callback_url
        from app.services.payment_gateway import create_payment, PaymentRequest

        get_settings.cache_clear()
        settings = get_settings()

        _print_section("Settings (from .env / env)")
        print(f"PAYMENT_PROVIDER: {getattr(settings, 'PAYMENT_PROVIDER', '')!r}")
        print(f"ZIBAL_SANDBOX: {getattr(settings, 'ZIBAL_SANDBOX', None)}")
        print(f"ZIBAL_MERCHANT: {_mask(getattr(settings, 'ZIBAL_MERCHANT', '') or '')}")
        cb = effective_payment_callback_url(settings)
        print(f"effective_payment_callback_url: {cb!r}")

        _print_section("create_payment (app service)")
        ref = f"logtest_{_utc_now().replace(':', '').replace('-', '')[:14]}"
        result = await create_payment(
            PaymentRequest(
                amount=1_100,
                description="scripts/test_zibal_connection.py",
                callback_url=cb,
                reference_id=ref,
                provider="zibal",
            )
        )
        print(f"success: {result.success}")
        print(f"authority (trackId): {(result.authority or '')[:40]!r}")
        print(f"payment_url: {(result.payment_url or '')[:120]!r}")
        print(f"ref_id: {result.ref_id!r}")
        print(f"error: {_safe_repr(result.error or '')}")

        _print_section("Direct httpx probe (gateway.zibal.ir)")
        try:
            import httpx

            mer = (getattr(settings, "ZIBAL_MERCHANT", "") or "").strip()
            payload = {
                "merchant": mer or "zibal",
                "amount": 1100,
                "callbackUrl": cb,
                "description": "probe",
                "orderId": ref + "_probe",
            }
            if bool(getattr(settings, "ZIBAL_SANDBOX", False)):
                payload["sandbox"] = True

            async with httpx.AsyncClient(timeout=25.0) as client:
                r = await client.post(
                    "https://gateway.zibal.ir/v1/request",
                    json=payload,
                )
            print(f"HTTP status: {r.status_code}")
            print(f"response body (first 500 chars): {r.text[:500]!r}")
        except Exception as e:
            print(f"probe FAILED: {type(e).__name__}: {e}")
            traceback.print_exc()

        _print_section("Summary")
        if result.success and result.payment_url:
            print("STATUS: OK - token/trackId received; open payment_url in browser.")
            return 0
        print("STATUS: FAIL - see error above; send this full log.")
        return 1

    except Exception as e:
        _print_section("FATAL")
        print(f"{type(e).__name__}: {e}")
        traceback.print_exc()
        return 2


if __name__ == "__main__":
    _configure_stdio_utf8()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")
    try:
        code = asyncio.run(main())
    except KeyboardInterrupt:
        print("\n(interrupted)")
        code = 130
    sys.exit(code)
