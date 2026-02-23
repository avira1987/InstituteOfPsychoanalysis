"""Payment API endpoints - create payment, handle callback, verify."""

import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.api.auth import get_current_user
from app.models.operational_models import User
from app.services.payment_gateway import (
    PaymentRequest, create_payment, verify_payment,
)
from app.services.payment_service import PaymentService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payment", tags=["Payment"])


class CreatePaymentRequest(BaseModel):
    amount: int
    description: str = "پرداخت هزینه جلسه"
    student_id: Optional[str] = None
    reference_id: Optional[str] = None
    mobile: Optional[str] = None


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
    """Create a payment request and get redirect URL."""
    payment_req = PaymentRequest(
        amount=req.amount,
        description=req.description,
        student_id=req.student_id,
        reference_id=req.reference_id or str(uuid.uuid4().hex[:16]),
        mobile=req.mobile,
    )
    result = await create_payment(payment_req)

    if result.success:
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
    """Handle callback from payment gateway (Saman or Zibal)."""
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

    if state == "OK" or str(status_code) in ("0", "100"):
        amount = int(data.get("Amount", data.get("amount", 0)))
        result = await verify_payment(str(ref_num), amount)

        if result.success:
            payment_svc = PaymentService(db)
            await payment_svc.record_payment(
                student_id=uuid.UUID(res_num) if _is_uuid(res_num) else uuid.uuid4(),
                amount=amount,
                description=f"پرداخت موفق | ref={result.ref_id}",
            )
            await db.commit()
            logger.info(f"[PAYMENT] Verified & recorded: ref={result.ref_id}")
            return {"success": True, "ref_id": result.ref_id, "message": "پرداخت با موفقیت انجام شد"}
        else:
            return {"success": False, "error": result.error}
    else:
        logger.warning(f"[PAYMENT] Failed callback: state={state}, status={status_code}")
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
