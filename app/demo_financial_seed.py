"""رکوردهای مالی دمو برای پر شدن داشبورد مالی (فقط وقتی جدول خالی است)."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import FinancialRecord, Student, User

logger = logging.getLogger(__name__)


def _at(base: datetime, days_ago: float) -> datetime:
    return base - timedelta(days=days_ago)


async def ensure_demo_financial_records(db: AsyncSession) -> int:
    """
    اگر هنوز هیچ رکورد مالی نیست، برای چند دانشجوی موجود ردیف‌های نمونه می‌سازد.
    idempotent: اگر حداقل یک رکورد باشد، کاری نمی‌کند.
    """
    existing = (await db.execute(select(func.count(FinancialRecord.id)))).scalar() or 0
    if existing > 0:
        return 0

    r = await db.execute(select(Student).order_by(Student.student_code.asc()).limit(12))
    students = list(r.scalars().all())
    if not students:
        logger.info("Demo financial seed skipped: no students in DB.")
        return 0

    ar = await db.execute(select(User).where(User.role == "admin").limit(1))
    admin = ar.scalars().first()
    admin_id = admin.id if admin else None
    now = datetime.now(timezone.utc)

    specs: list[tuple[str, float, str, float, int | None]] = [
        ("payment", 8_500_000, "پرداخت شهریه ترم — کارت به کارت", 52, 1403),
        ("debt", 2_100_000, "مانده اقساط ثبت‌شده (دوره آشنایی)", 38, 1403),
        ("payment", 5_200_000, "پرداخت آنلاین — درگاه بانکی", 41, 1403),
        ("credit", 500_000, "استرداد اضافه پرداخت — خواسته دانشجو", 35, 1403),
        ("payment", 12_000_000, "پرداخت یکجای شهریه جامع", 60, 1402),
        ("absence_fee", 350_000, "جریمه غیبت جلسه درمان (غیرموجه)", 22, 1403),
        ("debt", 3_800_000, "صورتحساب جلسات عقب‌افتاده", 15, 1403),
        ("payment", 3_800_000, "تسویه صورتحساب جلسات", 14, 1403),
        ("payment", 2_400_000, "پرداخت قسط دوم — واریز به حساب مرکز", 28, 1403),
        ("credit", 120_000, "بستانکاری از بابت تخفیف کمیته", 27, 1403),
        ("payment", 6_750_000, "واریز شهریه ترم دوم", 19, 1403),
        ("absence_fee", 280_000, "جریمه غیبت (عدم اطلاع به‌موقع)", 11, 1403),
        ("payment", 1_000_000, "پیش‌پرداخت ثبت‌نام", 90, 1402),
        ("debt", 1_500_000, "هزینه ثبت‌نام تکمیلی — صادر شده", 8, 1403),
        ("payment", 4_000_000, "پرداخت از محل اعتبار سازمانی", 5, 1403),
        ("payment", 3_200_000, "فیش بانکی — شعبه مرکزی", 3, 1403),
        ("credit", 200_000, "استرداد بابت لغو جلسه از سوی مرکز", 2, 1403),
        ("payment", 7_100_000, "تسویه نهایی پرونده مالی", 1, 1403),
    ]

    n = 0
    for i, (rtype, amount, desc, days_ago, sy) in enumerate(specs):
        st_id = students[i % len(students)].id
        db.add(
            FinancialRecord(
                id=uuid.uuid4(),
                student_id=st_id,
                record_type=rtype,
                amount=float(amount),
                description_fa=desc,
                reference_id=None,
                shamsi_year=sy,
                created_at=_at(now, days_ago),
                created_by=admin_id,
            )
        )
        n += 1

    await db.commit()
    logger.info("Demo financial records inserted: %s rows (students used=%s)", n, len(students))
    return n
