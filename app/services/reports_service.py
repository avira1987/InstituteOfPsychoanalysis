"""ساخت ردیف‌های خام گزارش از دیتابیس — فرمت خروجی در reports_formatters."""

from __future__ import annotations

import json
import uuid
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from typing import Any

import jdatetime
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models.audit_models import AuditLog
from app.models.operational_models import (
    AttendanceRecord,
    FinancialRecord,
    ProcessInstance,
    Student,
    TherapySession,
    User,
)

def shamsi_month_gregorian_range(shamsi_year: int, shamsi_month: int) -> tuple[date, date]:
    start_j = jdatetime.date(shamsi_year, shamsi_month, 1)
    if shamsi_month == 12:
        next_first = jdatetime.date(shamsi_year + 1, 1, 1)
    else:
        next_first = jdatetime.date(shamsi_year, shamsi_month + 1, 1)
    end_j = next_first - timedelta(days=1)
    return start_j.togregorian(), end_j.togregorian()


def shamsi_year_gregorian_range(shamsi_year: int) -> tuple[date, date]:
    start_j = jdatetime.date(shamsi_year, 1, 1)
    next_new_year = jdatetime.date(shamsi_year + 1, 1, 1)
    end_j = next_new_year - timedelta(days=1)
    return start_j.togregorian(), end_j.togregorian()


def _range_to_utc_bounds(d0: date, d1: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(d0, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(d1, time.max, tzinfo=timezone.utc)
    return start_dt, end_dt


def _context_data_as_dict(ctx: Any) -> dict[str, Any] | None:
    """context_data در DB گاهی dict و گاهی رشتهٔ JSON است."""
    if ctx is None:
        return None
    if isinstance(ctx, dict):
        return ctx
    if isinstance(ctx, str):
        s = ctx.strip()
        if not s:
            return None
        try:
            parsed: Any = json.loads(s)
        except (json.JSONDecodeError, TypeError):
            return None
        return parsed if isinstance(parsed, dict) else None
    return None


def _extract_violation_category(ctx: Any) -> str:
    d = _context_data_as_dict(ctx)
    if not d:
        return "نامشخص"
    for key in ("violation_category", "violation_type", "category", "نوع_تخلف"):
        v = d.get(key)
        if v:
            return str(v)
    return "نامشخص"


async def build_report1_rows(
    db: AsyncSession,
    shamsi_year: int,
    shamsi_month: int,
    *,
    include_sample_data: bool = False,
) -> list[list[Any]]:
    """گزارش ۱ — تخلف (فرایند violation_registration)."""
    d0, d1 = shamsi_month_gregorian_range(shamsi_year, shamsi_month)
    y0, y1 = shamsi_year_gregorian_range(shamsi_year)
    month_start, month_end = _range_to_utc_bounds(d0, d1)
    year_start, year_end = _range_to_utc_bounds(y0, y1)

    stmt = (
        select(ProcessInstance, Student, User)
        .join(Student, ProcessInstance.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .where(ProcessInstance.process_code == "violation_registration")
    )
    if not include_sample_data:
        stmt = stmt.where(Student.is_sample_data.is_(False))
    result = await db.execute(stmt)
    rows_db = result.all()

    # per student: total instances (lifetime), new instances started in month, category counts in month & year
    by_student: dict[uuid.UUID, dict[str, Any]] = {}
    cat_month: dict[str, int] = defaultdict(int)
    cat_year: dict[str, int] = defaultdict(int)

    for pi, st, u in rows_db:
        sid = st.id
        if sid not in by_student:
            by_student[sid] = {
                "name": u.full_name_fa or u.username,
                "code": st.student_code,
                "total_instances": 0,
                "new_in_month": 0,
            }
        by_student[sid]["total_instances"] += 1
        if pi.started_at and month_start <= pi.started_at <= month_end:
            by_student[sid]["new_in_month"] += 1
        cat = _extract_violation_category(pi.context_data)
        if pi.started_at and month_start <= pi.started_at <= month_end:
            cat_month[cat] += 1
        if pi.started_at and year_start <= pi.started_at <= year_end:
            cat_year[cat] += 1

    out: list[list[Any]] = []
    out.append(["کد دانشجو", "نام", "تعداد کل پرونده تخلف (از ابتدای تحصیل تا تاریخ گزارش)", "تخلف جدید ثبت‌شده در این ماه"])
    for sid in sorted(by_student.keys(), key=lambda x: by_student[x]["code"]):
        r = by_student[sid]
        out.append([r["code"], r["name"], r["total_instances"], r["new_in_month"]])
    out.append([])
    out.append(["دسته‌بندی (ماه جاری) — فراوانی"])
    out.append(["دسته", "تعداد در ماه"])
    for k in sorted(cat_month.keys()):
        out.append([k, cat_month[k]])
    out.append([])
    out.append(["دسته‌بندی (سال شمسی انتخاب‌شده) — تجمیع"])
    out.append(["دسته", "تعداد در سال"])
    for k in sorted(cat_year.keys()):
        out.append([k, cat_year[k]])

    return out


async def build_report2_rows(
    db: AsyncSession,
    shamsi_year: int,
    shamsi_month: int,
    *,
    include_sample_data: bool = False,
) -> list[list[Any]]:
    """گزارش ۲ — بدهی (رکوردهای debt؛ معوق = مانده منفی = بدهکار)."""
    d0, d1 = shamsi_month_gregorian_range(shamsi_year, shamsi_month)
    month_start, month_end = _range_to_utc_bounds(d0, d1)

    debt_q = (
        select(FinancialRecord.student_id, func.coalesce(func.sum(FinancialRecord.amount), 0.0))
        .where(FinancialRecord.record_type.in_(["debt", "absence_fee"]))
        .group_by(FinancialRecord.student_id)
    )
    pay_q = (
        select(FinancialRecord.student_id, func.coalesce(func.sum(FinancialRecord.amount), 0.0))
        .where(FinancialRecord.record_type.in_(["payment", "credit"]))
        .group_by(FinancialRecord.student_id)
    )
    debts = {row[0]: float(row[1]) for row in (await db.execute(debt_q)).all()}
    pays = {row[0]: float(row[1]) for row in (await db.execute(pay_q)).all()}
    all_ids = set(debts.keys()) | set(pays.keys())

    stmt = select(Student, User).join(User, Student.user_id == User.id)
    if not include_sample_data:
        stmt = stmt.where(Student.is_sample_data.is_(False))
    students = {s.id: (s, u) for s, u in (await db.execute(stmt)).all()}

    stmt_m = select(FinancialRecord).where(
        FinancialRecord.record_type == "debt",
        FinancialRecord.created_at >= month_start,
        FinancialRecord.created_at <= month_end,
    )
    month_debts = (await db.execute(stmt_m)).scalars().all()

    provider_counts: dict[str, int] = defaultdict(int)
    detail_rows: list[list[Any]] = []
    for rec in month_debts:
        st_u = students.get(rec.student_id)
        if not st_u:
            continue
        st, u = st_u
        prov = "نامشخص"
        d = rec.description_fa or ""
        if "شهریه" in d or "قسط" in d:
            prov = "شهریه/قسط"
        elif "سوپرو" in d or "supervision" in d.lower():
            prov = "سوپرویژن"
        elif "درمان" in d:
            prov = "درمان (بر اساس شرح)"
        provider_counts[prov] += 1
        detail_rows.append(
            [st.student_code, u.full_name_fa or u.username, rec.amount, d, prov]
        )

    out: list[list[Any]] = []
    out.append(
        [
            "توضیح",
            "معوق: مانده منفی (جمع پرداختها منهای جمع بدهیها) — مطابق ثبت مالی سامانه",
        ]
    )
    out.append(["کد دانشجو", "نام", "مانده (منفی=بدهکار)", "جمع بدهی ثبت‌شده", "جمع پرداخت/اعتبار"])
    for sid in sorted(all_ids, key=lambda x: students[x][0].student_code if x in students else ""):
        if sid not in students:
            continue
        st, u = students[sid]
        bal = pays.get(sid, 0.0) - debts.get(sid, 0.0)
        if bal >= 0:
            continue
        out.append(
            [
                st.student_code,
                u.full_name_fa or u.username,
                round(bal, 0),
                debts.get(sid, 0),
                pays.get(sid, 0),
            ]
        )
    out.append([])
    out.append(["ریز نوبت‌های بدهی ثبت‌شده در این ماه"])
    out.append(["کد دانشجو", "نام", "مبلغ", "شرح", "نوع خدمات‌دهنده (تقریبی)"])
    out.extend(detail_rows)
    out.append([])
    out.append(["تعداد نوبت بدهی در ماه به تفکیک نوع خدمات‌دهنده"])
    out.append(["نوع", "تعداد نوبت"])
    for k in sorted(provider_counts.keys()):
        out.append([k, provider_counts[k]])

    return out


async def build_report3_rows(
    db: AsyncSession,
    shamsi_year: int,
    shamsi_month: int,
    *,
    include_sample_data: bool = False,
) -> list[list[Any]]:
    """گزارش ۳ — ریزش / انصراف (فرایند ثبت‌نام جامع گیرکرده پس از پذیرش)."""
    d0, d1 = shamsi_month_gregorian_range(shamsi_year, shamsi_month)
    month_start, month_end = _range_to_utc_bounds(d0, d1)
    # پذیرفته‌شده اما هنوز ثبت‌نام نهایی نکرده
    stuck_states = ("result_accepted", "course_display", "payment")
    stmt = (
        select(ProcessInstance, Student, User)
        .join(Student, ProcessInstance.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .where(
            ProcessInstance.process_code == "comprehensive_course_registration",
            ProcessInstance.is_completed.is_(False),
            ProcessInstance.is_cancelled.is_(False),
            ProcessInstance.current_state_code.in_(stuck_states),
        )
    )
    if not include_sample_data:
        stmt = stmt.where(Student.is_sample_data.is_(False))
    stuck = (await db.execute(stmt)).all()

    # انصراف / مرخصی در ماه: فرایند educational_leave
    leave_stmt = (
        select(ProcessInstance, Student, User)
        .join(Student, ProcessInstance.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .where(
            ProcessInstance.process_code == "educational_leave",
            ProcessInstance.last_transition_at >= month_start,
            ProcessInstance.last_transition_at <= month_end,
        )
    )
    if not include_sample_data:
        leave_stmt = leave_stmt.where(Student.is_sample_data.is_(False))
    leaves = (await db.execute(leave_stmt)).all()

    out: list[list[Any]] = []
    out.append(["بخش الف — پذیرفته در مصاحبه، ثبت‌نام نهایی انجام نشده (وضعیت جاری)"])
    out.append(["کد دانشجو", "نام", "وضعیت فعلی فرایند", "آخرین تغییر"])
    for pi, st, u in stuck:
        out.append(
            [
                st.student_code,
                u.full_name_fa or u.username,
                pi.current_state_code,
                pi.last_transition_at.isoformat() if pi.last_transition_at else "",
            ]
        )
    out.append([])
    out.append(["بخش ب — فرایند مرخصی آموزشی با آخرین جابه‌جایی در این ماه"])
    out.append(["کد دانشجو", "نام", "وضعیت", "آخرین تغییر"])
    for pi, st, u in leaves:
        out.append(
            [
                st.student_code,
                u.full_name_fa or u.username,
                pi.current_state_code,
                pi.last_transition_at.isoformat() if pi.last_transition_at else "",
            ]
        )

    return out


async def build_report4_rows(
    db: AsyncSession,
    shamsi_year: int,
    shamsi_month: int,
    *,
    include_sample_data: bool = False,
) -> list[list[Any]]:
    """گزارش ۴ — نقض مهلت (لاگ audit با sla_breach)."""
    d0, d1 = shamsi_month_gregorian_range(shamsi_year, shamsi_month)
    month_start, month_end = _range_to_utc_bounds(d0, d1)
    stmt = (
        select(AuditLog)
        .outerjoin(ProcessInstance, AuditLog.instance_id == ProcessInstance.id)
        .outerjoin(Student, ProcessInstance.student_id == Student.id)
        .where(
            AuditLog.action_type == "sla_breach",
            AuditLog.timestamp >= month_start,
            AuditLog.timestamp <= month_end,
        )
    )
    if not include_sample_data:
        stmt = stmt.where(
            or_(
                AuditLog.instance_id.is_(None),
                Student.id.is_(None),
                Student.is_sample_data.is_(False),
            )
        )
    stmt = stmt.order_by(AuditLog.timestamp.desc())
    logs = (await db.execute(stmt)).scalars().all()

    by_role: dict[str, int] = defaultdict(int)
    out: list[list[Any]] = []
    out.append(["زمان", "فرایند", "از وضعیت", "به وضعیت", "نقش بازیگر", "نام بازیگر", "جزئیات"])
    for log in logs:
        role = log.actor_role or ""
        by_role[role] += 1
        det = ""
        if log.details:
            det = str(log.details)[:500]
        out.append(
            [
                log.timestamp.isoformat() if log.timestamp else "",
                log.process_code or "",
                log.from_state or "",
                log.to_state or "",
                role,
                log.actor_name or "",
                det,
            ]
        )
    out.append([])
    out.append(["تعداد به تفکیک نقش"])
    out.append(["نقش", "تعداد"])
    for k in sorted(by_role.keys()):
        out.append([k or "(نامشخص)", by_role[k]])

    return out


async def build_report5_rows(
    db: AsyncSession,
    shamsi_year: int,
    shamsi_month: int,
    *,
    include_sample_data: bool = False,
) -> list[list[Any]]:
    """گزارش ۵ — کنسلی جلسات درمان و غیبت‌ها."""
    d0, d1 = shamsi_month_gregorian_range(shamsi_year, shamsi_month)
    Therapist = aliased(User)
    t_stmt2 = (
        select(TherapySession, Student, User, Therapist)
        .join(Student, TherapySession.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .outerjoin(Therapist, TherapySession.therapist_id == Therapist.id)
        .where(
            TherapySession.status == "cancelled",
            TherapySession.session_date >= d0,
            TherapySession.session_date <= d1,
        )
    )
    if not include_sample_data:
        t_stmt2 = t_stmt2.where(Student.is_sample_data.is_(False))
    ts_rows = (await db.execute(t_stmt2)).all()

    att_stmt = (
        select(AttendanceRecord, Student, User)
        .join(Student, AttendanceRecord.student_id == Student.id)
        .join(User, Student.user_id == User.id)
        .where(
            AttendanceRecord.record_date >= d0,
            AttendanceRecord.record_date <= d1,
            AttendanceRecord.status.in_(["absent_excused", "absent_unexcused"]),
        )
    )
    if not include_sample_data:
        att_stmt = att_stmt.where(Student.is_sample_data.is_(False))
    att_rows = (await db.execute(att_stmt)).all()

    out: list[list[Any]] = []
    out.append(["بخش الف — جلسات درمان با وضعیت لغو در این ماه"])
    out.append(["تاریخ جلسه", "کد دانشجو", "نام دانشجو", "نام درمانگر", "وضعیت"])
    for ts, st, u, th_user in ts_rows:
        th_name = th_user.full_name_fa if th_user else ""
        out.append([str(ts.session_date), st.student_code, u.full_name_fa or u.username, th_name, ts.status])
    out.append([])
    out.append(["بخش ب — غیبت ثبت‌شده در این ماه"])
    out.append(["تاریخ", "کد دانشجو", "نام", "وضعیت", "نوع غیبت", "یادداشت"])
    for ar, st, u in att_rows:
        out.append(
            [
                str(ar.record_date),
                st.student_code,
                u.full_name_fa or u.username,
                ar.status,
                ar.absence_type or "",
                (ar.notes or "")[:200],
            ]
        )

    return out
