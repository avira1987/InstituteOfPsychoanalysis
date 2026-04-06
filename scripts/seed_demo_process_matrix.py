"""
ایجاد دادهٔ دمو برای پنل ادمین: یک دانشجوی تستی به ازای هر فرایند (AUTO-DEMO-*)
به‌علاوه سناریوهای شاخه‌ای ثبت‌نام آشنایی (DEMO-SCEN-*).

اجرا (پس از migrate و تنظیم .env):

  python scripts/seed_demo_process_matrix.py --all
  python scripts/seed_demo_process_matrix.py --matrix
  python scripts/seed_demo_process_matrix.py --scenarios
  python scripts/seed_demo_process_matrix.py --all --force

ورود پنل: همیشه admin / admin123 (همان کاربر پیش‌فرض اپ) — تب «ورود با رمز عبور»، نه پیامک؛ ابتدا چالش ریاضی را پاس کنید.
متغیر اختیاری: DEMO_MATRIX_STUDENT_PASSWORD (رمز دانشجویان دمو)
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys

# قبل از import اپ — جلوگیری از SMS واقعی
os.environ.setdefault("SMS_PROVIDER", "log")
os.environ.setdefault("OTP_RESTRICT_TO_STUDENT_PHONES", "false")

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


async def _main() -> int:
    parser = argparse.ArgumentParser(description="Seed demo students for process matrix / scenarios")
    parser.add_argument(
        "--matrix",
        action="store_true",
        help="One demo student per process (AUTO-DEMO-*) plus greedy walk",
    )
    parser.add_argument(
        "--scenarios",
        action="store_true",
        help="Intro registration branch scenarios (DEMO-SCEN-*)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Run scenarios then full matrix (سناریوها اول برای دیدن سریع‌تر در پنل)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing AUTO-DEMO-* and DEMO-SCEN-* students then re-seed",
    )
    args = parser.parse_args()

    if not (args.matrix or args.scenarios or args.all):
        args.all = True

    do_matrix = args.matrix or args.all
    do_scenarios = args.scenarios or args.all

    from app.database import async_session_factory
    from app.demo_process_walker import (
        delete_demo_seed_users,
        seed_branch_scenarios,
        seed_full_matrix,
    )

    demo_pass = os.environ.get("DEMO_MATRIX_STUDENT_PASSWORD", "demo_student_123")

    async with async_session_factory() as db:
        if args.force:
            if do_matrix and do_scenarios:
                prefixes = ("AUTO-DEMO-", "DEMO-SCEN-")
            elif do_matrix:
                prefixes = ("AUTO-DEMO-",)
            else:
                prefixes = ("DEMO-SCEN-",)
            n = await delete_demo_seed_users(db, prefixes=prefixes)
            logger.info("Removed %s prior demo seed rows (prefixes=%s)", n, prefixes)

        if do_scenarios:
            codes = await seed_branch_scenarios(
                db,
                None,
                None,
                demo_pass,
            )
            print(json.dumps(codes, ensure_ascii=False, indent=2))

        if do_matrix:
            report = await seed_full_matrix(
                db,
                None,
                None,
                demo_pass,
            )
            print(json.dumps(report, ensure_ascii=False, indent=2))
            logger.info(
                "Matrix: completed_ok=%s stuck=%s",
                report.get("ok_count"),
                report.get("stuck_count"),
            )

    print(
        "\n--- Admin UI login (use PASSWORD tab, not SMS) ---",
        "  1) Switch to the password login tab.",
        "  2) Solve the math challenge, then enter credentials.",
        "  3) username: admin",
        "     password: admin123",
        f"  Demo student users password: {demo_pass!r}",
        sep="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
