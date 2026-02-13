"""Payment Service - Handles payment processing, invoicing, and financial records."""

import uuid
import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.operational_models import FinancialRecord, TherapySession, Student

logger = logging.getLogger(__name__)


class PaymentResult:
    """Result of a payment operation."""
    def __init__(self, success: bool, transaction_id: Optional[str] = None,
                 amount: float = 0, message: str = "", error: str = ""):
        self.success = success
        self.transaction_id = transaction_id
        self.amount = amount
        self.message = message
        self.error = error

    def to_dict(self):
        return {
            "success": self.success,
            "transaction_id": self.transaction_id,
            "amount": self.amount,
            "message": self.message,
            "error": self.error,
        }


class PaymentService:
    """Service for handling payments and financial records."""

    # Base fee per therapy session (configurable per process metadata)
    DEFAULT_SESSION_FEE = 500_000  # Toman (placeholder)
    DEFAULT_EXTRA_SESSION_FEE = 750_000

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_session_fee(
        self,
        student_id: uuid.UUID,
        session_type: str = "regular",
        custom_amount: Optional[float] = None,
    ) -> float:
        """Calculate the fee for a therapy session."""
        if custom_amount is not None:
            return custom_amount

        if session_type == "extra":
            return self.DEFAULT_EXTRA_SESSION_FEE
        return self.DEFAULT_SESSION_FEE

    async def generate_invoice(
        self,
        student_id: uuid.UUID,
        amount: float,
        description: str,
        reference_id: Optional[uuid.UUID] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> FinancialRecord:
        """Generate a payment invoice (debt record)."""
        record = FinancialRecord(
            id=uuid.uuid4(),
            student_id=student_id,
            record_type="debt",
            amount=amount,
            description_fa=description,
            reference_id=reference_id,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        logger.info(f"Invoice generated: student={student_id}, amount={amount}, desc={description}")
        return record

    async def record_payment(
        self,
        student_id: uuid.UUID,
        amount: float,
        description: str = "پرداخت هزینه جلسه",
        reference_id: Optional[uuid.UUID] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> PaymentResult:
        """Record a payment (placeholder for actual payment gateway integration)."""
        # In production, integrate with payment gateway here
        record = FinancialRecord(
            id=uuid.uuid4(),
            student_id=student_id,
            record_type="payment",
            amount=amount,
            description_fa=description,
            reference_id=reference_id,
            created_by=created_by,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(record)

        logger.info(f"Payment recorded: student={student_id}, amount={amount}")
        return PaymentResult(
            success=True,
            transaction_id=str(record.id),
            amount=amount,
            message="پرداخت با موفقیت ثبت شد",
        )

    async def process_refund(
        self,
        student_id: uuid.UUID,
        amount: float,
        reason: str = "استرداد هزینه",
        reference_id: Optional[uuid.UUID] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> PaymentResult:
        """Process a refund (credit record)."""
        record = FinancialRecord(
            id=uuid.uuid4(),
            student_id=student_id,
            record_type="credit",
            amount=amount,
            description_fa=reason,
            reference_id=reference_id,
            created_by=created_by,
        )
        self.db.add(record)

        return PaymentResult(
            success=True,
            transaction_id=str(record.id),
            amount=amount,
            message="استرداد ثبت شد",
        )

    async def charge_absence_fee(
        self,
        student_id: uuid.UUID,
        session_id: Optional[uuid.UUID] = None,
        amount: Optional[float] = None,
        created_by: Optional[uuid.UUID] = None,
    ) -> FinancialRecord:
        """Charge a fee for an absence."""
        fee = amount or self.DEFAULT_SESSION_FEE
        record = FinancialRecord(
            id=uuid.uuid4(),
            student_id=student_id,
            record_type="absence_fee",
            amount=fee,
            description_fa="هزینه غیبت جلسه درمان",
            reference_id=session_id,
            created_by=created_by,
        )
        self.db.add(record)
        return record

    async def get_student_balance(self, student_id: uuid.UUID) -> dict:
        """Get the financial balance for a student."""
        # Total payments
        payments_stmt = select(func.coalesce(func.sum(FinancialRecord.amount), 0)).where(
            FinancialRecord.student_id == student_id,
            FinancialRecord.record_type == "payment",
        )
        payments_result = await self.db.execute(payments_stmt)
        total_payments = payments_result.scalar()

        # Total credits (refunds)
        credits_stmt = select(func.coalesce(func.sum(FinancialRecord.amount), 0)).where(
            FinancialRecord.student_id == student_id,
            FinancialRecord.record_type == "credit",
        )
        credits_result = await self.db.execute(credits_stmt)
        total_credits = credits_result.scalar()

        # Total debts
        debts_stmt = select(func.coalesce(func.sum(FinancialRecord.amount), 0)).where(
            FinancialRecord.student_id == student_id,
            FinancialRecord.record_type.in_(["debt", "absence_fee"]),
        )
        debts_result = await self.db.execute(debts_stmt)
        total_debts = debts_result.scalar()

        balance = (total_payments + total_credits) - total_debts

        return {
            "student_id": str(student_id),
            "total_payments": float(total_payments),
            "total_credits": float(total_credits),
            "total_debts": float(total_debts),
            "balance": float(balance),
            "has_outstanding_debt": balance < 0,
        }

    async def get_student_financial_history(
        self,
        student_id: uuid.UUID,
        limit: int = 50,
    ) -> list[dict]:
        """Get financial transaction history for a student."""
        stmt = (
            select(FinancialRecord)
            .where(FinancialRecord.student_id == student_id)
            .order_by(FinancialRecord.created_at.desc())
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        records = result.scalars().all()

        return [
            {
                "id": str(r.id),
                "type": r.record_type,
                "amount": r.amount,
                "description": r.description_fa,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]

    async def waive_fee(
        self,
        record_id: uuid.UUID,
        reason: str = "بخشودگی",
        approved_by: Optional[uuid.UUID] = None,
    ) -> PaymentResult:
        """Waive a fee (create offsetting credit)."""
        stmt = select(FinancialRecord).where(FinancialRecord.id == record_id)
        result = await self.db.execute(stmt)
        record = result.scalars().first()
        if not record:
            return PaymentResult(success=False, error="Record not found")

        waiver = FinancialRecord(
            id=uuid.uuid4(),
            student_id=record.student_id,
            record_type="credit",
            amount=record.amount,
            description_fa=f"بخشودگی: {reason}",
            reference_id=record_id,
            created_by=approved_by,
        )
        self.db.add(waiver)
        return PaymentResult(
            success=True,
            transaction_id=str(waiver.id),
            amount=record.amount,
            message="هزینه بخشیده شد",
        )
