#!/usr/bin/env python3
"""
قرار دادن دانشجوی student1 روی وضعیت اولیهٔ فرایند ثبت‌نام دوره آشنایی
(application_submitted). دادهٔ فرم پذیرش وب اکنون در همان مرحلهٔ ثبت‌نام/تکمیل
پنل (با کد ملی) جمع می‌شود؛ فرم تکراری admission_form از متادیتا حذف شده است.
این اسکریپت برای خالی کردن context مرحلهٔ اول (در صورت نیاز تست) است.

اجرا از ریشهٔ مخزن (با DATABASE_URL معتبر در .env):

  python scripts/put_student1_at_intro_first_form.py
"""
from __future__ import annotations

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
from app.models.operational_models import User, Student, ProcessInstance
from app.core.engine import StateMachineEngine
from app.meta.student_step_forms import CTX_SUBMITTED, CTX_EDIT_UNLOCK

PROCESS_CODE = "introductory_course_registration"
FIRST_STATE = "application_submitted"
STUDENT_USERNAME = "student1"

# فیلدهای فرم admission_form — برای تست خالی دیدن فرم
_ADMISSION_KEYS = {
    "full_name",
    "national_code",
    "phone",
    "email",
    "education_level",
    "field_of_study",
    "motivation",
}


def _scrub_context_for_first_form(ctx: dict | None) -> dict:
    out = dict(ctx or {})
    for k in _ADMISSION_KEYS:
        out.pop(k, None)
    sub = dict(out.get(CTX_SUBMITTED) or {})
    sub.pop(FIRST_STATE, None)
    out[CTX_SUBMITTED] = sub
    unlock = dict(out.get(CTX_EDIT_UNLOCK) or {})
    unlock.pop(FIRST_STATE, None)
    out[CTX_EDIT_UNLOCK] = unlock
    return out


async def main() -> int:
    async with async_session_factory() as db:
        r = await db.execute(select(User).where(User.username == STUDENT_USERNAME))
        u = r.scalars().first()
        if not u:
            print(f"ERROR: user {STUDENT_USERNAME!r} not found. Run scripts/seed_demo_users.py first.")
            return 1

        r = await db.execute(select(Student).where(Student.user_id == u.id))
        student = r.scalars().first()
        if not student:
            print(f"ERROR: no Student row for {STUDENT_USERNAME}")
            return 1

        r = await db.execute(select(User).where(User.role == "admin").limit(1))
        admin = r.scalars().first()
        if not admin:
            print("ERROR: no admin user — need at least one admin to attribute start_process")
            return 1

        r = await db.execute(
            select(ProcessInstance)
            .where(
                ProcessInstance.student_id == student.id,
                ProcessInstance.process_code == PROCESS_CODE,
                ProcessInstance.is_completed.is_(False),
                ProcessInstance.is_cancelled.is_(False),
            )
            .order_by(ProcessInstance.started_at.desc())
        )
        inst = r.scalars().first()

        if inst:
            inst.current_state_code = FIRST_STATE
            inst.context_data = _scrub_context_for_first_form(inst.context_data)
            flag_modified(inst, "context_data")
            await db.commit()
            print(f"OK: updated existing instance {inst.id}")
        else:
            engine = StateMachineEngine(db)
            inst = await engine.start_process(
                process_code=PROCESS_CODE,
                student_id=student.id,
                actor_id=admin.id,
                actor_role="admin",
                initial_context={},
            )
            # مطمئن شویم روی همان state اولیه و بدون قفل ثبت قبلی
            inst.current_state_code = FIRST_STATE
            inst.context_data = _scrub_context_for_first_form(inst.context_data)
            flag_modified(inst, "context_data")
            await db.commit()
            print(f"OK: started new instance {inst.id}")

        print()
        print("ورود به پنل دانشجو: student1 / demo123")
        print(f"مسیر: /panel/portal/student — فرایند «ثبت‌نام دوره آشنایی» را باز کنید.")
        print(f"instance_id (برای اتوماسیون): {inst.id}")
        print(f"current_state: {FIRST_STATE} — فرم «فرم پذیرش (وب‌سایت)» باید دیده شود.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
