#!/usr/bin/env python3
"""مهاجرت نمونه‌های گیرکردهٔ start_therapy در therapist_confirmation.

پس از sync تعریف فرایند (حذف گیت تأیید درمانگر)، نمونه‌هایی که هنوز در
`therapist_confirmation` مانده‌اند را با این اسکریپت جلو ببرید.

Usage:
  python scripts/migrate_start_therapy_stuck_confirmation.py --dry-run
  python scripts/migrate_start_therapy_stuck_confirmation.py --apply
  python scripts/migrate_start_therapy_stuck_confirmation.py --apply --release

--apply: اعمال schedule + رفتن به payment_pending (معادل مسیر جدید پس از انتخاب)
--release: به‌جای جلو بردن، اسلات‌ها را آزاد و به therapist_selection برگردان

پیش‌نیاز: python scripts/sync_one_process_from_json.py --code start_therapy
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_start_therapy_stuck")


async def _run(*, apply: bool, release: bool) -> int:
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    from app.database import AsyncSessionLocal
    from app.models.operational_models import ProcessInstance
    from app.services.action_handler import ActionHandler

    async with AsyncSessionLocal() as db:
        rows = list(
            (
                await db.execute(
                    select(ProcessInstance).where(
                        ProcessInstance.process_code == "start_therapy",
                        ProcessInstance.current_state_code == "therapist_confirmation",
                        ProcessInstance.is_completed == False,  # noqa: E712
                        ProcessInstance.is_cancelled == False,  # noqa: E712
                    )
                )
            )
            .scalars()
            .all()
        )
        logger.info("found %s stuck instance(s)", len(rows))
        if not rows:
            return 0

        for inst in rows:
            logger.info("instance=%s student=%s", inst.id, inst.student_id)
            if not apply:
                continue

            handler = ActionHandler(db)
            if release:
                await handler.handle_actions(
                    [
                        {"type": "release_therapist_slots_to_available_sheet"},
                        {
                            "type": "reopen_student_step_forms",
                            "state": "therapist_selection",
                            "clear_keys": [
                                "therapist_id",
                                "slot_ids",
                                "booked_slot_ids",
                                "selected_slots_summary_fa",
                                "weekly_sessions",
                            ],
                        },
                    ],
                    inst,
                    {},
                )
                inst.current_state_code = "therapist_selection"
                flag_modified(inst, "context_data")
                await db.flush()
                logger.info("  -> released to therapist_selection")
                continue

            # جلو بردن: state موقت + apply schedule (nested → payment_pending)
            inst.current_state_code = "first_session_24h_check"
            await db.flush()
            msg = await handler.handle_actions(
                [{"type": "apply_start_therapy_session_schedule"}],
                inst,
                dict(inst.context_data or {}),
            )
            await db.refresh(inst)
            logger.info("  -> after schedule state=%s msg=%s", inst.current_state_code, msg)

        if apply:
            await db.commit()
            logger.info("committed")
        else:
            logger.info("dry-run only; pass --apply to mutate")
        return len(rows)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true", help="فقط شمارش (پیش‌فرض اگر --apply نباشد)")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--release", action="store_true", help="آزادسازی اسلات و برگشت به انتخاب")
    args = p.parse_args()
    n = asyncio.run(_run(apply=bool(args.apply), release=bool(args.release)))
    raise SystemExit(0 if n >= 0 else 1)


if __name__ == "__main__":
    main()
