"""
دادهٔ دمو آماده‌سازی ترم (INST-OPS): پاییز منتشرشده + زمستان در زمان‌بندی اسلات.

  python scripts/seed_semester_prep_demo.py
  python scripts/seed_semester_prep_demo.py --replace
  python scripts/seed_semester_prep_demo.py --winter-published

پیشنهاد برای جلوگیری از SMS واقعی:
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
    parser = argparse.ArgumentParser(description="Seed semester prep demo on INST-OPS anchor")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="حذف نمونه‌های prep قبلی روی INST-OPS و ایجاد مجدد",
    )
    parser.add_argument(
        "--winter-published",
        action="store_true",
        help="زمستان هم تا published کامل شود (پیش‌فرض: توقف در interview_scheduling)",
    )
    args = parser.parse_args()

    from app.database import async_session_factory
    from app.seed_semester_prep_demo import seed_semester_prep_demo

    winter_stop = "published" if args.winter_published else "interview_scheduling"

    async with async_session_factory() as db:
        report = await seed_semester_prep_demo(
            db,
            replace=args.replace,
            winter_stop_state=winter_stop,
        )
        print(json.dumps(report, ensure_ascii=False, indent=2))

    print(
        "\n--- ورود پیشنهادی ---",
        "  ادمین / معاون آموزش: admin یا deputy_education1 — رمزها در login_hints",
        "  مسئول سایت (اسلات): site_manager1 / demo123",
        "  صفحه آماده‌سازی ترم: /panel/semester-prep",
        sep="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
