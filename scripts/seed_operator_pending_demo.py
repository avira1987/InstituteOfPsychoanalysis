"""
ایجاد دانشجویان دمو DEMO-OP-* در وضعیت «منتظر اقدام اپراتور».

  python scripts/seed_operator_pending_demo.py
  python scripts/seed_operator_pending_demo.py --replace

نیاز: دیتابیس مهاجرت‌شده و .env؛ برای جلوگیری از SMS واقعی:
  set SMS_PROVIDER=log
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

os.environ.setdefault("SMS_PROVIDER", "log")
os.environ.setdefault("OTP_RESTRICT_TO_STUDENT_PHONES", "false")

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


async def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--replace",
        action="store_true",
        help="حذف DEMO-OP-* قبلی و ایجاد مجدد",
    )
    args = parser.parse_args()

    from app.database import async_session_factory
    from app.seed_operator_pending_demo import seed_operator_pending_demo

    demo_pass = os.environ.get("DEMO_MATRIX_STUDENT_PASSWORD", "demo_student_123")

    async with async_session_factory() as db:
        report = await seed_operator_pending_demo(db, demo_pass, replace=args.replace)
        print(json.dumps(report, ensure_ascii=False, indent=2))

    print(
        "\n--- ورود ---",
        "  ادمین: admin / admin123 (تب رمز، نه پیامک)",
        f"  رمز دانشجویان دمو: {demo_pass!r}",
        sep="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
