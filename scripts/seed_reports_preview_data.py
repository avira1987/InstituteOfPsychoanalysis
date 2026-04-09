#!/usr/bin/env python3
"""
دادهٔ نمایشی برای بررسی خروجی پنج گزارش مدیریتی (تخلف، بدهی، ریزش، SLA، کنسلی/غیبت).

پیش‌نیاز: جداول با Alembic ساخته شده باشند.
اتصال: همان DATABASE_URL پروژه (یا env).

دانشجویان با کد REPORT-SEED-0x و is_sample_data=False تا در گزارش‌های عادی (بدون تیک «نمونه»)
و در سایر بخش‌ها دیده شوند. برای حذف و اجرای مجدد:  --force

استفاده:
  python scripts/seed_reports_preview_data.py
  python scripts/seed_reports_preview_data.py --force
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import date, datetime, time, timedelta, timezone

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

sys.path.insert(0, str(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import bcrypt
import jdatetime
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

def _pwd_hash(p: str) -> str:
    return bcrypt.hashpw(p.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _utc_bounds(d0: date, d1: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(d0, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(d1, time.max, tzinfo=timezone.utc)
    return start_dt, end_dt


def _shamsi_month_gregorian_range(shamsi_year: int, shamsi_month: int) -> tuple[date, date]:
    start_j = jdatetime.date(shamsi_year, shamsi_month, 1)
    if shamsi_month == 12:
        next_first = jdatetime.date(shamsi_year + 1, 1, 1)
    else:
        next_first = jdatetime.date(shamsi_year, shamsi_month + 1, 1)
    end_j = next_first - timedelta(days=1)
    return start_j.togregorian(), end_j.togregorian()


def _now_shamsi_month() -> tuple[int, int]:
    now = jdatetime.datetime.now()
    return now.year, now.month


async def _cleanup(session: AsyncSession, user_ids: list[uuid.UUID], student_ids: list[uuid.UUID]) -> None:
    from app.models.audit_models import AuditLog
    from app.models.operational_models import (
        AttendanceRecord,
        FinancialRecord,
        ProcessInstance,
        Student,
        TherapySession,
        User,
    )

    if student_ids:
        await session.execute(delete(FinancialRecord).where(FinancialRecord.student_id.in_(student_ids)))
        await session.execute(delete(AttendanceRecord).where(AttendanceRecord.student_id.in_(student_ids)))
        await session.execute(delete(TherapySession).where(TherapySession.student_id.in_(student_ids)))

        inst_ids = (
            await session.execute(select(ProcessInstance.id).where(ProcessInstance.student_id.in_(student_ids)))
        ).scalars().all()
        if inst_ids:
            await session.execute(delete(AuditLog).where(AuditLog.instance_id.in_(inst_ids)))
        await session.execute(delete(ProcessInstance).where(ProcessInstance.student_id.in_(student_ids)))
        await session.execute(delete(Student).where(Student.id.in_(student_ids)))
    for uid in user_ids:
        await session.execute(delete(User).where(User.id == uid))


async def seed(session: AsyncSession, *, force: bool) -> None:
    from app.models.audit_models import AuditLog
    from app.models.operational_models import (
        AttendanceRecord,
        FinancialRecord,
        ProcessInstance,
        Student,
        TherapySession,
        User,
    )

    PREFIX = "REPORT-SEED-"
    usernames = [
        "report_seed_stu1",
        "report_seed_stu2",
        "report_seed_stu3",
        "report_seed_stu4",
        "report_seed_therapist",
    ]
    existing = (
        await session.execute(select(User.id).where(User.username.in_(usernames)))
    ).scalars().all()
    if existing and not force:
        print(
            "کاربران report_seed_* از قبل وجود دارند. برای پر کردن مجدد:  python scripts/seed_reports_preview_data.py --force"
        )
        return

    if existing and force:
        users_all = (await session.execute(select(User).where(User.username.in_(usernames)))).scalars().all()
        user_by_name = {u.username: u for u in users_all}
        st_rows = (
            await session.execute(
                select(Student).where(Student.student_code.like(f"{PREFIX}%"))
            )
        ).scalars().all()
        student_ids = [s.id for s in st_rows]
        user_ids = [u.id for u in users_all]
        await _cleanup(session, user_ids, student_ids)
        await session.flush()
        print("دادهٔ قبلی REPORT-SEED حذف شد.")

    sy, sm = _now_shamsi_month()
    d0, d1 = _shamsi_month_gregorian_range(sy, sm)
    month_start, month_end = _utc_bounds(d0, d1)
    ts_mid = month_start + (month_end - month_start) / 2
    day_in_month = min(d0 + timedelta(days=7), d1)
    pwd = _pwd_hash("ReportPreview123!")

    def user_row(
        username: str,
        full_name: str,
        role: str,
        email: str,
    ) -> User:
        return User(
            id=uuid.uuid4(),
            username=username,
            email=email,
            hashed_password=pwd,
            full_name_fa=full_name,
            role=role,
            is_active=True,
            phone="09120000000",
        )

    u_ther = user_row(
        "report_seed_therapist",
        "دکتر نمونه درمانگر (گزارشات)",
        "therapist",
        "report_seed_therapist@preview.local",
    )
    u1 = user_row("report_seed_stu1", "دانشجوی نمونه الف — تخلف و بدهی", "student", "report_seed_stu1@preview.local")
    u2 = user_row("report_seed_stu2", "دانشجوی نمونه ب — ثبت‌نام جامع", "student", "report_seed_stu2@preview.local")
    u3 = user_row("report_seed_stu3", "دانشجوی نمونه ج — مرخصی", "student", "report_seed_stu3@preview.local")
    u4 = user_row("report_seed_stu4", "دانشجوی نمونه د — جلسه و غیبت", "student", "report_seed_stu4@preview.local")

    for u in (u_ther, u1, u2, u3, u4):
        session.add(u)

    st1 = Student(
        id=uuid.uuid4(),
        user_id=u1.id,
        student_code=f"{PREFIX}01",
        course_type="comprehensive",
        is_intern=False,
        term_count=2,
        current_term=2,
        therapy_started=True,
        weekly_sessions=2,
        therapist_id=u_ther.id,
        enrollment_date=d0,
        is_sample_data=False,
    )
    st2 = Student(
        id=uuid.uuid4(),
        user_id=u2.id,
        student_code=f"{PREFIX}02",
        course_type="comprehensive",
        is_intern=False,
        term_count=1,
        current_term=1,
        therapy_started=False,
        weekly_sessions=1,
        is_sample_data=False,
    )
    st3 = Student(
        id=uuid.uuid4(),
        user_id=u3.id,
        student_code=f"{PREFIX}03",
        course_type="introductory",
        is_intern=False,
        term_count=1,
        current_term=1,
        therapy_started=True,
        weekly_sessions=1,
        therapist_id=u_ther.id,
        is_sample_data=False,
    )
    st4 = Student(
        id=uuid.uuid4(),
        user_id=u4.id,
        student_code=f"{PREFIX}04",
        course_type="comprehensive",
        is_intern=False,
        term_count=3,
        current_term=2,
        therapy_started=True,
        weekly_sessions=2,
        therapist_id=u_ther.id,
        is_sample_data=False,
    )
    for s in (st1, st2, st3, st4):
        session.add(s)

    await session.flush()

    # ─── گزارش ۱: تخلف — چند نمونه با دسته‌های مختلف در همین ماه ───
    pi_v1 = ProcessInstance(
        id=uuid.uuid4(),
        process_code="violation_registration",
        student_id=st1.id,
        current_state_code="registered",
        is_completed=False,
        is_cancelled=False,
        context_data={"violation_category": "تأخیر تحویل گزارش"},
        started_at=ts_mid,
        last_transition_at=ts_mid,
        started_by=u_ther.id,
    )
    pi_v2 = ProcessInstance(
        id=uuid.uuid4(),
        process_code="violation_registration",
        student_id=st1.id,
        current_state_code="registered",
        is_completed=False,
        is_cancelled=False,
        context_data={"violation_category": "عدم حضور در جلسه آموزشی"},
        started_at=month_start + timedelta(days=1),
        last_transition_at=month_start + timedelta(days=1),
        started_by=u_ther.id,
    )
    session.add_all([pi_v1, pi_v2])

    # ─── گزارش ۲: بدهی (مانده منفی) + ریز نوبت بدهی در ماه ───
    session.add_all(
        [
            FinancialRecord(
                id=uuid.uuid4(),
                student_id=st1.id,
                record_type="debt",
                amount=12_000_000.0,
                description_fa="شهریه و قسط ترم جاری — ثبت سیستمی",
                shamsi_year=sy,
                created_at=month_start + timedelta(hours=10),
            ),
            FinancialRecord(
                id=uuid.uuid4(),
                student_id=st1.id,
                record_type="debt",
                amount=2_500_000.0,
                description_fa="سوپرویژن ماهانه",
                shamsi_year=sy,
                created_at=month_start + timedelta(days=2, hours=14),
            ),
            FinancialRecord(
                id=uuid.uuid4(),
                student_id=st1.id,
                record_type="debt",
                amount=1_800_000.0,
                description_fa="جلسه درمان فردی",
                shamsi_year=sy,
                created_at=month_start + timedelta(days=4, hours=9),
            ),
            FinancialRecord(
                id=uuid.uuid4(),
                student_id=st1.id,
                record_type="payment",
                amount=5_000_000.0,
                description_fa="پرداخت کارت به کارت — تأیید مالی",
                shamsi_year=sy,
                created_at=month_start + timedelta(days=5, hours=11),
            ),
        ]
    )
    # جمع بدهی 16.3M، پرداخت 5M → مانده منفی

    # ─── گزارش ۳ الف: ثبت‌نام جامع گیرکرده ───
    pi_comp = ProcessInstance(
        id=uuid.uuid4(),
        process_code="comprehensive_course_registration",
        student_id=st2.id,
        current_state_code="result_accepted",
        is_completed=False,
        is_cancelled=False,
        context_data={"note": "نمونه گزارش — منتظر تکمیل ثبت‌نام"},
        started_at=month_start - timedelta(days=20),
        last_transition_at=month_start + timedelta(days=3),
        started_by=u_ther.id,
    )
    session.add(pi_comp)

    # ─── گزارش ۳ ب: مرخصی آموزشی — جابه‌جایی در ماه جاری ───
    pi_leave = ProcessInstance(
        id=uuid.uuid4(),
        process_code="educational_leave",
        student_id=st3.id,
        current_state_code="under_review",
        is_completed=False,
        is_cancelled=False,
        context_data={},
        started_at=month_start - timedelta(days=40),
        last_transition_at=ts_mid,
        started_by=u_ther.id,
    )
    session.add(pi_leave)

    await session.flush()

    # ─── گزارش ۴: نقض SLA — لاگ مرتبط با یک فرایند واقعی ───
    session.add(
        AuditLog(
            id=uuid.uuid4(),
            instance_id=pi_comp.id,
            process_code="comprehensive_course_registration",
            action_type="sla_breach",
            from_state="result_accepted",
            to_state="result_accepted",
            trigger_event="sla_check",
            actor_id=u_ther.id,
            actor_role="therapist",
            actor_name=u_ther.full_name_fa,
            details={"message": "نمونه نقض مهلت برای پیش‌نمایش گزارش"},
            timestamp=ts_mid,
        )
    )

    # ─── گزارش ۵ الف: جلسه درمان لغوشده ───
    session.add(
        TherapySession(
            id=uuid.uuid4(),
            student_id=st4.id,
            therapist_id=u_ther.id,
            session_date=day_in_month,
            session_number=3,
            status="cancelled",
            is_extra=False,
            payment_status="pending",
            amount=350_000.0,
            notes="لغو توسط مرکز — نمونه گزارش",
        )
    )

    # ─── گزارش ۵ ب: غیبت ───
    session.add(
        AttendanceRecord(
            id=uuid.uuid4(),
            student_id=st4.id,
            session_id=None,
            record_date=min(d0 + timedelta(days=12), d1),
            status="absent_excused",
            absence_type="student",
            shamsi_year=sy,
            notes="غیبت موجه — نمونه گزارش",
        )
    )

    await session.commit()
    print(f"پایان. بازهٔ شمسی هدف: {sy}/{sm:02d}  (میلادی: {d0} تا {d1})")
    print("کاربران: report_seed_stu1 … stu4 (دانشجو)، report_seed_therapist (درمانگر)")
    print("رمز یکسان برای همه: ReportPreview123!")
    print("در پنل گزارشات همان سال/ماه شمسی جاری را انتخاب کنید.")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Seed دادهٔ پیش‌نمایش گزارشات")
    parser.add_argument("--force", action="store_true", help="حذف دادهٔ REPORT-SEED قبلی و ایجاد مجدد")
    args = parser.parse_args()

    from app.database import async_session_factory

    async with async_session_factory() as session:
        try:
            await seed(session, force=args.force)
        except Exception as e:
            await session.rollback()
            print(f"خطا: {e}")
            raise
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
