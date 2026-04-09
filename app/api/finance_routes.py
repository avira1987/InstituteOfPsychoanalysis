"""Financial summary, transaction review, student balances, CSV export (اپراتور مالی / مدیر)."""

from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import require_role
from app.models.operational_models import User, FinancialRecord, Student
from app.services.installment_settings_service import get_installment_policy, update_installment_policy

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/finance", tags=["Finance"])


def _education_accounting_context() -> dict[str, Any]:
    """راهنمای هم‌راستا با مراکز آموزشی و گزارش‌گیری حسابداری (متن ثابت برای UI)."""
    return {
        "title": "هم‌ترازی با حسابداری و مراکز آموزشی",
        "intro": (
            "این سامانه رکوردهای مالی را برای هر دانشجو نگه می‌دارد. برای تطبیق با دفاتر رسمی و "
            "استانداردهای سازمان، خروجی CSV را در Excel یا نرم‌افزار حسابداری باز کنید و "
            "طبق شماره‌گذاری و سرفصل‌های تعریف‌شده در مرکز خود طبقه‌بندی کنید."
        ),
        "sections": [
            {
                "heading": "انواع رکورد در سیستم",
                "items": [
                    "پرداخت: وجه دریافت‌شده از دانشجو یا واریز به حساب مرکز.",
                    "بستانکاری / استرداد: کاهش بدهی یا بازگشت وجه به دانشجو.",
                    "بدهی: شهریه، اقساط یا هزینه‌های ثبت‌شده به عنوان مطالبه.",
                    "جریمه غیبت: هزینه‌های مرتبط با غیبت جلسات درمانی طبق آیین‌نامه.",
                ],
            },
            {
                "heading": "مانده هر دانشجو",
                "items": [
                    "فرمول نمایش‌داده‌شده: (جمع پرداخت‌ها + جمع بستانکاری‌ها) − (جمع بدهی و جریمه).",
                    "مانده منفی یعنی بدهی معوق نسبت به مطالبات ثبت‌شده؛ مثبت یعنی پیش‌پرداخت یا طلب دانشجو.",
                    "تعریف دقیق «بدهی قابل وصول» ممکن است با سیاست مالی مرکز و قراردادها متفاوت باشد.",
                ],
            },
            {
                "heading": "ارتباط با حسابداری",
                "items": [
                    "خروجی CSV را می‌توان به عنوان سند کمکی (یادداشت) به همراه اسناد بانکی و قراردادها بایگانی کرد.",
                    "در مراکز چند واحدی، کد دانشجو را با کد پرونده مالی در نرم‌افزار حسابداری تطبیق دهید.",
                    "سال شمسی (در صورت ثبت در رکورد) برای بستن دوره مالی مفید است.",
                ],
            },
        ],
    }


@router.get("/summary")
async def finance_summary(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("finance")),
):
    """Aggregate totals for dashboard (اپراتور مالی یا مدیر سیستم)."""
    pay = await db.execute(
        select(func.coalesce(func.sum(FinancialRecord.amount), 0)).where(
            FinancialRecord.record_type == "payment"
        )
    )
    cred = await db.execute(
        select(func.coalesce(func.sum(FinancialRecord.amount), 0)).where(
            FinancialRecord.record_type == "credit"
        )
    )
    debt = await db.execute(
        select(func.coalesce(func.sum(FinancialRecord.amount), 0)).where(
            FinancialRecord.record_type.in_(["debt", "absence_fee"])
        )
    )
    cnt = await db.execute(select(func.count(FinancialRecord.id)))
    total_payments = float(pay.scalar() or 0)
    total_credits = float(cred.scalar() or 0)
    total_debts = float(debt.scalar() or 0)
    record_count = int(cnt.scalar() or 0)

    # Per-type sums and counts for practical breakdown (مسائل مالی / گزارش‌گیری)
    br = await db.execute(
        select(
            FinancialRecord.record_type,
            func.count(FinancialRecord.id),
            func.coalesce(func.sum(FinancialRecord.amount), 0),
        ).group_by(FinancialRecord.record_type)
    )
    breakdown: dict = {}
    for row in br.all():
        rt, n, sm = row[0], int(row[1]), float(row[2] or 0)
        breakdown[rt] = {"count": n, "sum": sm}

    pay_n = breakdown.get("payment", {}).get("count") or 0
    net_cash_after_credits = total_payments - total_credits
    # ساده: بدهی‌های ثبت‌شده در برابر نقد خالص (فقط شاخص؛ تعریف دقیق بستگی به فرآیند دارد)
    net_vs_charges = net_cash_after_credits - total_debts
    avg_payment = (total_payments / pay_n) if pay_n else None

    return {
        "total_payments": total_payments,
        "total_credits": total_credits,
        "total_debts": total_debts,
        "record_count": record_count,
        "net_cash_after_credits": net_cash_after_credits,
        "net_vs_charges": net_vs_charges,
        "avg_payment": avg_payment,
        "breakdown": breakdown,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/context")
async def finance_education_context(
    current_user: User = Depends(require_role("finance")),
):
    """راهنمای هم‌ترازی با حسابداری و مراکز آموزشی (متن ثابت برای پنل)."""
    return _education_accounting_context()


class InstallmentPolicyPatch(BaseModel):
    """به‌روزرسانی جزئی سیاست اقساط."""

    term2_installment_gap_days: Optional[int] = Field(None, ge=1, le=365)
    installment_count_options: Optional[list[int]] = None


@router.get("/installment-settings")
async def finance_get_installment_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("finance")),
):
    """خواندن تنظیمات اقساط (سررسید بین اقساط ترم دوم، گزینه‌های تعداد قسط برای وب‌سایت)."""
    return await get_installment_policy(db)


@router.patch("/installment-settings")
async def finance_patch_installment_settings(
    body: InstallmentPolicyPatch,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("finance")),
):
    """ذخیرهٔ تنظیمات اقساط توسط اپراتور مالی یا مدیر."""
    return await update_installment_policy(
        db,
        term2_installment_gap_days=body.term2_installment_gap_days,
        installment_count_options=body.installment_count_options,
    )


@router.get("/transactions")
async def finance_transactions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("finance")),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    record_type: Optional[str] = Query(None, description="payment|credit|debt|absence_fee"),
    q: Optional[str] = Query(None, description="کد دانشجو، نام، شرح"),
):
    """فهرست تراکنش‌ها با صفحه‌بندی و فیلتر برای بررسی روزمره."""
    base = (
        select(FinancialRecord, Student.student_code, User.full_name_fa)
        .join(Student, Student.id == FinancialRecord.student_id)
        .join(User, User.id == Student.user_id)
    )
    if record_type:
        base = base.where(FinancialRecord.record_type == record_type)
    if q and q.strip():
        term = f"%{q.strip()}%"
        base = base.where(
            or_(
                Student.student_code.ilike(term),
                User.full_name_fa.ilike(term),
                FinancialRecord.description_fa.ilike(term),
            )
        )

    count_stmt = select(func.count()).select_from(base.subquery())
    total = int((await db.execute(count_stmt)).scalar() or 0)

    offset = (page - 1) * page_size
    stmt = (
        base.order_by(FinancialRecord.created_at.desc())
        .offset(offset)
        .limit(page_size)
    )
    r = await db.execute(stmt)
    rows = r.all()

    items = []
    for rec, code, name_fa in rows:
        items.append(
            {
                "id": str(rec.id),
                "student_code": code,
                "student_name_fa": name_fa,
                "record_type": rec.record_type,
                "amount": float(rec.amount),
                "description_fa": rec.description_fa,
                "shamsi_year": rec.shamsi_year,
                "created_at": rec.created_at.isoformat() if rec.created_at else None,
            }
        )

    pages = max(1, (total + page_size - 1) // page_size) if page_size else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
    }


@router.get("/student-balances")
async def finance_student_balances(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("finance")),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    only_debtors: bool = Query(False, description="فقط دانشجویان با مانده منفی"),
    sort: str = Query("balance_asc", description="balance_asc|balance_desc|code_asc"),
):
    """مانده مالی هر دانشجو (هم‌فرمول PaymentService.get_student_balance)."""
    pay_sum = func.coalesce(
        func.sum(
            case(
                (FinancialRecord.record_type == "payment", FinancialRecord.amount),
                else_=0,
            )
        ),
        0,
    )
    cred_sum = func.coalesce(
        func.sum(
            case(
                (FinancialRecord.record_type == "credit", FinancialRecord.amount),
                else_=0,
            )
        ),
        0,
    )
    deb_sum = func.coalesce(
        func.sum(
            case(
                (FinancialRecord.record_type.in_(("debt", "absence_fee")), FinancialRecord.amount),
                else_=0,
            )
        ),
        0,
    )

    inner = (
        select(
            FinancialRecord.student_id.label("student_id"),
            pay_sum.label("payments"),
            cred_sum.label("credits"),
            deb_sum.label("debts"),
        )
        .group_by(FinancialRecord.student_id)
    ).subquery()

    balance_expr = (inner.c.payments + inner.c.credits - inner.c.debts).label("balance")

    stmt = (
        select(
            inner.c.student_id,
            inner.c.payments,
            inner.c.credits,
            inner.c.debts,
            balance_expr,
            Student.student_code,
            User.full_name_fa,
        )
        .select_from(inner)
        .join(Student, Student.id == inner.c.student_id)
        .join(User, User.id == Student.user_id)
    )
    if only_debtors:
        stmt = stmt.where(balance_expr < 0)

    if sort == "balance_desc":
        stmt = stmt.order_by(balance_expr.desc(), Student.student_code.asc())
    elif sort == "code_asc":
        stmt = stmt.order_by(Student.student_code.asc())
    else:
        stmt = stmt.order_by(balance_expr.asc(), Student.student_code.asc())

    count_base = (
        select(inner.c.student_id)
        .select_from(inner)
        .join(Student, Student.id == inner.c.student_id)
        .join(User, User.id == Student.user_id)
    )
    if only_debtors:
        count_base = count_base.where(balance_expr < 0)
    count_stmt = select(func.count()).select_from(count_base.subquery())
    total = int((await db.execute(count_stmt)).scalar() or 0)

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    r = await db.execute(stmt)
    out_rows = r.all()

    items = []
    for row in out_rows:
        sid, pay, cred, deb, bal, scode, name_fa = row
        items.append(
            {
                "student_id": str(sid),
                "student_code": scode,
                "student_name_fa": name_fa,
                "total_payments": float(pay or 0),
                "total_credits": float(cred or 0),
                "total_debts": float(deb or 0),
                "balance": float(bal or 0),
                "has_outstanding_debt": float(bal or 0) < 0,
            }
        )

    pages = max(1, (total + page_size - 1) // page_size) if page_size else 1
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "sort": sort,
        "only_debtors": only_debtors,
    }


@router.get("/export.csv")
async def export_financial_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("finance")),
    limit: int = Query(5000, le=20000),
):
    """Download financial records as CSV for accounting (اپراتور مالی یا مدیر سیستم)."""
    stmt = (
        select(FinancialRecord, Student.student_code)
        .join(Student, Student.id == FinancialRecord.student_id)
        .order_by(FinancialRecord.created_at.desc())
        .limit(limit)
    )
    r = await db.execute(stmt)
    rows = r.all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "student_code", "record_type", "amount", "description_fa", "created_at"])
    for rec, code in rows:
        w.writerow(
            [
                str(rec.id),
                code,
                rec.record_type,
                rec.amount,
                (rec.description_fa or "").replace("\n", " "),
                rec.created_at.isoformat() if rec.created_at else "",
            ]
        )
    buf.seek(0)
    logger.info(
        "finance_csv_export user=%s rows=%s",
        current_user.username,
        len(rows),
    )
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="financial_records.csv"'},
    )
