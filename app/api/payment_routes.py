"""Payment API endpoints - create payment, handle callback, verify.

BUILD_TODO § و (بخش ۶): Callback drives session_payment via payment_successful/unsuccessful.
"""

import uuid
import logging
from typing import Optional
from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.operational_models import User, ProcessInstance, PaymentPending
from app.services.payment_gateway import (
    PaymentRequest, create_payment, verify_payment,
)
from app.services.payment_service import PaymentService
from app.core.engine import StateMachineEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payment", tags=["Payment"])


class CreatePaymentRequest(BaseModel):
    amount: int
    description: str = "پرداخت هزینه جلسه"
    student_id: Optional[str] = None
    reference_id: Optional[str] = None
    mobile: Optional[str] = None
    instance_id: Optional[str] = None  # session_payment instance for callback → transition


class PaymentCallbackData(BaseModel):
    """Fields that payment gateways typically send back."""
    State: Optional[str] = None
    RefNum: Optional[str] = None
    ResNum: Optional[str] = None
    TraceNo: Optional[str] = None
    SecurePan: Optional[str] = None
    Status: Optional[int] = None
    trackId: Optional[str] = None
    success: Optional[int] = None
    orderId: Optional[str] = None


@router.post("/create")
async def create_payment_endpoint(
    req: CreatePaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a payment request and get redirect URL. If instance_id is set (e.g. session_payment), callback will run transition."""
    payment_req = PaymentRequest(
        amount=req.amount,
        description=req.description,
        student_id=req.student_id,
        reference_id=req.reference_id or str(uuid.uuid4().hex[:16]),
        mobile=req.mobile,
    )
    result = await create_payment(payment_req)

    if result.success:
        if req.instance_id and _is_uuid(req.instance_id) and req.student_id and _is_uuid(req.student_id):
            pending = PaymentPending(
                id=uuid.uuid4(),
                authority=result.authority,
                instance_id=uuid.UUID(req.instance_id),
                student_id=uuid.UUID(req.student_id),
                amount=req.amount,
            )
            db.add(pending)
            await db.flush()
        return {
            "success": True,
            "payment_url": result.payment_url,
            "authority": result.authority,
        }
    else:
        raise HTTPException(status_code=400, detail=result.error)


@router.post("/callback")
async def payment_callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle callback from payment gateway. On success/failure, run session_payment transition if pending (BUILD_TODO § و)."""
    try:
        content_type = request.headers.get("content-type", "")
        if "json" in content_type:
            data = await request.json()
        else:
            form = await request.form()
            data = dict(form)
    except Exception:
        data = dict(request.query_params)

    logger.info(f"[PAYMENT-CALLBACK] Received: {data}")

    ref_num = data.get("RefNum") or data.get("trackId") or data.get("authority", "")
    state = data.get("State", "")
    status_code = data.get("Status")
    res_num = data.get("ResNum") or data.get("orderId", "")
    amount = int(data.get("Amount", data.get("amount", 0)) or 0)

    pending = None
    if ref_num:
        r = await db.execute(select(PaymentPending).where(PaymentPending.authority == ref_num).limit(1))
        pending = r.scalars().first()

    if state == "OK" or str(status_code) in ("0", "100"):
        result = await verify_payment(str(ref_num), amount)

        if result.success:
            student_id = pending.student_id if pending else (uuid.UUID(res_num) if _is_uuid(res_num) else None)
            if not student_id:
                student_id = uuid.uuid4()
            payment_svc = PaymentService(db)
            await payment_svc.record_payment(
                student_id=student_id,
                amount=amount,
                description=f"پرداخت موفق | ref={result.ref_id}",
            )
            if pending:
                instance_id = pending.instance_id
                r = await db.execute(select(ProcessInstance).where(ProcessInstance.id == instance_id))
                inst = r.scalars().first()
                if inst and inst.process_code == "session_payment" and inst.current_state_code == "awaiting_payment" and not inst.is_completed:
                    engine = StateMachineEngine(db)
                    system_actor_id = await _get_system_actor_id(db)
                    try:
                        await engine.execute_transition(
                            instance_id=instance_id,
                            trigger_event="payment_successful",
                            actor_id=system_actor_id,
                            actor_role="system",
                            payload={"amount": amount, "ref_id": result.ref_id},
                        )
                        logger.info(
                            "[PAYMENT] session_payment_ok instance_id=%s student_id=%s amount=%s ref=%s",
                            instance_id,
                            str(pending.student_id),
                            amount,
                            getattr(result, "ref_id", ""),
                        )
                    except Exception as e:
                        logger.exception(f"[PAYMENT] Transition payment_successful failed: {e}")
                await db.delete(pending)
            await db.commit()
            logger.info(f"[PAYMENT] Verified & recorded: ref={result.ref_id}")
            return {"success": True, "ref_id": result.ref_id, "message": "پرداخت با موفقیت انجام شد"}
        else:
            if pending:
                await _fire_payment_unsuccessful(db, pending)
            await db.commit()
            return {"success": False, "error": result.error}
    else:
        logger.warning(f"[PAYMENT] Failed callback: state={state}, status_code={status_code}")
        if pending:
            await _fire_payment_unsuccessful(db, pending)
        await db.commit()
        return {"success": False, "error": "پرداخت ناموفق بود"}


@router.post("/verify")
async def verify_payment_endpoint(
    authority: str,
    amount: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually verify a payment."""
    result = await verify_payment(authority, amount)
    return result.to_dict()


def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except (ValueError, AttributeError):
        return False


async def _get_system_actor_id(db: AsyncSession) -> uuid.UUID:
    """Return first admin user id for system-triggered transitions (e.g. payment callback)."""
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row:
        return row[0]
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row[0] if row else uuid.uuid4()


async def _fire_payment_unsuccessful(db: AsyncSession, pending: PaymentPending) -> None:
    """Run session_payment transition payment_unsuccessful when callback reports failure."""
    r = await db.execute(select(ProcessInstance).where(ProcessInstance.id == pending.instance_id))
    inst = r.scalars().first()
    if not inst or inst.process_code != "session_payment" or inst.current_state_code != "awaiting_payment" or inst.is_completed:
        return
    engine = StateMachineEngine(db)
    system_actor_id = await _get_system_actor_id(db)
    try:
        await engine.execute_transition(
            instance_id=pending.instance_id,
            trigger_event="payment_unsuccessful",
            actor_id=system_actor_id,
            actor_role="system",
        )
        logger.info(f"[PAYMENT] session_payment transition payment_unsuccessful for instance {pending.instance_id}")
    except Exception as e:
        logger.exception(f"[PAYMENT] Transition payment_unsuccessful failed: {e}")
    await db.delete(pending)
