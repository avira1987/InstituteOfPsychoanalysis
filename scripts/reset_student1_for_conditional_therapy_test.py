#!/usr/bin/env python3
"""
صفر کردن همهٔ فرایندها و فلگ‌های درمان/پذیرش برای student1
تا بتوان از اول ثبت‌نام دوره آشنایی + مسیر مشروطی درمان را تست کرد.

اجرا از ریشهٔ مخزن:

  python scripts/reset_student1_for_conditional_therapy_test.py

ورود بعد از اجرا: student1 / demo123
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

from sqlalchemy import delete, select, update
from sqlalchemy.orm.attributes import flag_modified

from app.database import async_session_factory
from app.models.operational_models import (
    AttendanceRecord,
    EducationalTherapistSlot,
    FinancialRecord,
    ProcessInstance,
    Student,
    TherapySession,
    User,
)
from app.core.engine import StateMachineEngine

STUDENT_USERNAME = "student1"
PROCESS_CODE = "introductory_course_registration"


async def main() -> int:
    async with async_session_factory() as db:
        r = await db.execute(select(User).where(User.username == STUDENT_USERNAME))
        u = r.scalars().first()
        if not u:
            print(f"ERROR: user {STUDENT_USERNAME!r} not found. Run: python scripts/seed_demo_users.py")
            return 1

        r = await db.execute(select(Student).where(Student.user_id == u.id))
        student = r.scalars().first()
        if not student:
            print(f"ERROR: no Student row for {STUDENT_USERNAME}")
            return 1

        r = await db.execute(select(User).where(User.role == "admin").limit(1))
        admin = r.scalars().first()
        if not admin:
            print("ERROR: no admin user")
            return 1

        sid = student.id

        # آزاد کردن اسلات درمانگر آموزشی در صورت انتساب
        try:
            await db.execute(
                update(EducationalTherapistSlot)
                .where(EducationalTherapistSlot.assigned_student_id == sid)
                .values(assigned_student_id=None, status="available")
            )
        except Exception as e:
            print(f"WARN: slot release skipped: {e}")

        n_fin = (await db.execute(delete(FinancialRecord).where(FinancialRecord.student_id == sid))).rowcount
        n_att = (await db.execute(delete(AttendanceRecord).where(AttendanceRecord.student_id == sid))).rowcount
        n_sess = (await db.execute(delete(TherapySession).where(TherapySession.student_id == sid))).rowcount

        # StateHistory و وابستگی‌های CASCADE با حذف نمونه پاک می‌شوند
        n_inst = (
            await db.execute(delete(ProcessInstance).where(ProcessInstance.student_id == sid))
        ).rowcount

        # ریست پرونده دانشجو برای شروع از صفر (دوره آشنایی)
        student.course_type = "introductory"
        student.therapy_started = False
        student.therapist_id = None
        student.weekly_sessions = 1
        student.term_count = 1
        student.current_term = 1
        student.is_intern = False
        student.extra_data = {
            "reset_for": "conditional_therapy_manual_test",
        }
        flag_modified(student, "extra_data")

        engine = StateMachineEngine(db)
        inst = await engine.start_process(
            process_code=PROCESS_CODE,
            student_id=student.id,
            actor_id=admin.id,
            actor_role="admin",
            initial_context={
                "source": "reset_student1_for_conditional_therapy_test",
            },
        )
        # primary path روی ثبت‌نام تازه
        from app.services.student_service import StudentService

        await StudentService(db).set_primary_instance_for_student(student, inst.id)
        await db.commit()

        print("OK: student1 reset")
        print(f"  deleted instances={n_inst} sessions={n_sess} attendance={n_att} financial={n_fin}")
        print(f"  therapy_started=False  admission_type cleared")
        print(f"  new intro registration instance: {inst.id}")
        print(f"  current_state: {inst.current_state_code}")
        print()
        print("ورود: student1 / demo123")
        print("پنل: /panel/portal/student")
        print()
        print("--- مسیر تست مشروطی (خلاصه) ---")
        print("1) با interviewer/پذیرش نتیجه مصاحبه را «پذیرش مشروط به درمان» بزنید")
        print("2) مدارک → انتخاب درس → پرداخت تا registration_complete")
        print("3) داشبورد: کارت «پذیرش مشروط…» + SMS مهلت + فرایند start_therapy")
        print("4) دکمه کارت → ادامه آغاز درمان؛ یا تکمیل درمان و بعد تست گیت ترم ۲")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
