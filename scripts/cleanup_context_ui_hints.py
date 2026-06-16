#!/usr/bin/env python3
"""
پاک‌سازی/یکتاسازی کلید فنی ``ui_hints`` در ``context_data`` همهٔ نمونه‌های فرایند.

این کلید فقط «راهنمای فنی UI» برای اکشن‌های یکپارچه‌سازی است
(scheduled_notification، schedule_reminder و…) و دادهٔ پروندهٔ دانشجو نیست.
به‌دلیل افزودن بدون کنترل تکرار، در پرونده‌های قدیمی به‌صورت انبوه و تکراری انباشته شده است.

حالت‌های اجرا:
  - یکتاسازی (پیش‌فرض): فقط آیتم‌های تکراری حذف می‌شوند.
  - حذف کامل (--drop): کل کلید ui_hints از context_data حذف می‌شود.

ابتدا بدون نوشتن در دیتابیس گزارش می‌دهد؛ برای اعمال واقعی باید --apply بدهید.

اجرا از ریشهٔ مخزن (با DATABASE_URL معتبر در .env):

  python scripts/cleanup_context_ui_hints.py                 # گزارش یکتاسازی (dry-run)
  python scripts/cleanup_context_ui_hints.py --apply         # اعمال یکتاسازی
  python scripts/cleanup_context_ui_hints.py --drop --apply  # حذف کامل ui_hints
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session_factory
from app.models.operational_models import ProcessInstance


def _dedupe_hints(hints: list) -> list:
    """حذف تکرارها با حفظ ترتیب اولین رخداد."""
    seen: list = []
    out: list = []
    for h in hints:
        if h not in seen:
            seen.append(h)
            out.append(h)
    return out


async def main() -> int:
    parser = argparse.ArgumentParser(description="پاک‌سازی ui_hints در context_data")
    parser.add_argument("--drop", action="store_true", help="حذف کامل کلید ui_hints به‌جای یکتاسازی")
    parser.add_argument("--apply", action="store_true", help="اعمال واقعی تغییرات (بدون آن فقط گزارش)")
    args = parser.parse_args()

    scanned = 0
    affected = 0
    removed_items = 0

    async with async_session_factory() as db:
        result = await db.execute(select(ProcessInstance))
        instances = result.scalars().all()

        for inst in instances:
            scanned += 1
            ctx = inst.context_data
            if not isinstance(ctx, dict):
                continue
            hints = ctx.get("ui_hints")
            if not isinstance(hints, list) or not hints:
                continue

            if args.drop:
                removed_items += len(hints)
                ctx.pop("ui_hints", None)
                affected += 1
                if args.apply:
                    inst.context_data = ctx
                    flag_modified(inst, "context_data")
                continue

            deduped = _dedupe_hints(hints)
            if len(deduped) == len(hints):
                continue
            removed_items += len(hints) - len(deduped)
            affected += 1
            if args.apply:
                ctx["ui_hints"] = deduped
                inst.context_data = ctx
                flag_modified(inst, "context_data")

        if args.apply:
            await db.commit()

    mode = "حذف کامل" if args.drop else "یکتاسازی"
    state = "اعمال شد" if args.apply else "(dry-run — چیزی نوشته نشد)"
    print(f"حالت: {mode} {state}")
    print(f"تعداد نمونه‌های بررسی‌شده: {scanned}")
    print(f"تعداد نمونه‌های تغییرکرده: {affected}")
    print(f"تعداد آیتم‌های حذف‌شده از ui_hints: {removed_items}")
    if not args.apply and affected:
        print("\nبرای اعمال واقعی، دوباره با --apply اجرا کنید.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
