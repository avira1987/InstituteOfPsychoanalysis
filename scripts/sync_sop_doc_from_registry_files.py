#!/usr/bin/env python3
"""
همگام‌سازی متن و تصویر SOP از پوشهٔ رجیستری به جدول process_definitions.

فایل‌ها (نسبت به ریشهٔ مخزن):
  metadata/process_registry/processes/{code}/SOP_document.txt
  metadata/process_registry/processes/{code}/SOP_flowchart.png  (اختیاری)

همچنین در صورت نیاز sop_order=1 در config ادغام می‌شود (برای educational_leave).

اجرا (با DATABASE_URL معتبر، مثلاً داخل کانتینر api):
  python scripts/sync_sop_doc_from_registry_files.py
  python scripts/sync_sop_doc_from_registry_files.py --code educational_leave --dry-run
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
from app.models.meta_models import ProcessDefinition


def _merge_sop_order(cfg: dict | None, order: int) -> dict:
    out = dict(cfg) if isinstance(cfg, dict) else {}
    out.setdefault("sop_order", order)
    return out


async def run(*, code: str, dry_run: bool, sop_order: int | None = None) -> int:
    base = os.path.join(ROOT, "metadata", "process_registry", "processes", code)
    text_path = os.path.join(base, "SOP_document.txt")
    img_path = os.path.join(base, "SOP_flowchart.png")

    if not os.path.isfile(text_path):
        print(f"خطا: فایل متن یافت نشد: {text_path}", file=sys.stderr)
        return 1

    text = open(text_path, encoding="utf-8").read()
    img_bytes: bytes | None = None
    content_type: str | None = None
    if os.path.isfile(img_path):
        img_bytes = open(img_path, "rb").read()
        lower = img_path.lower()
        if lower.endswith(".png"):
            content_type = "image/png"
        elif lower.endswith(".jpg") or lower.endswith(".jpeg"):
            content_type = "image/jpeg"
        elif lower.endswith(".webp"):
            content_type = "image/webp"
        elif lower.endswith(".gif"):
            content_type = "image/gif"
        else:
            content_type = "image/png"

    print(f"code={code}")
    print(f"text: {text_path} ({len(text)} chars)")
    print(f"image: {img_path} ({len(img_bytes) if img_bytes else 0} bytes)")

    if dry_run:
        print("dry-run: بدون تغییر در دیتابیس")
        return 0

    async with async_session_factory() as session:
        r = await session.execute(select(ProcessDefinition).where(ProcessDefinition.code == code))
        p = r.scalar_one_or_none()
        if p is None:
            print(f"خطا: فرایندی با code={code!r} در دیتابیس نیست. ابتدا متادیتا را sync کنید.", file=sys.stderr)
            return 1

        p.source_text = text
        if img_bytes is not None:
            p.flowchart_image = img_bytes
            p.flowchart_content_type = content_type
        if sop_order is not None:
            p.config = _merge_sop_order(p.config, sop_order)
            flag_modified(p, "config")
        p.version = (p.version or 1) + 1
        await session.commit()
        print(f"به‌روز شد: {p.name_fa} (id={p.id}, version={p.version})")
    return 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--code", default="educational_leave", help="کد فرایند در DB")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument(
        "--sop-order",
        type=int,
        default=None,
        help="در صورت ارسال، sop_order در config درج می‌شود؛ برای educational_leave پیش‌فرض ۱ است",
    )
    args = ap.parse_args()
    sop = args.sop_order
    if sop is None and args.code == "educational_leave":
        sop = 1
    rc = asyncio.run(run(code=args.code, dry_run=args.dry_run, sop_order=sop))
    sys.exit(rc)


if __name__ == "__main__":
    main()
