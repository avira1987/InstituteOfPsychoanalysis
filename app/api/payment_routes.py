"""Payment API endpoints - create payment, handle callback, verify.

BUILD_TODO § و (بخش ۶): Callback drives session_payment via payment_successful/unsuccessful.
Amounts sent to Shaparak SEP are in Rials; internal ledger (FinancialRecord) uses Toman.
"""

import uuid
import logging
from typing import Any, Optional
from urllib.parse import urlencode

from sqlalchemy import select
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.config import get_settings
from app.database import get_db
from app.api.auth import get_current_user
from app.models.operational_models import User, ProcessInstance, PaymentPending
from app.services.payment_gateway import (
    PaymentRequest,
    create_payment,
    verify_payment,
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


def _callback_wants_json(request: Request) -> bool:
    """پاسخ JSON برای تست/ادغام؛ در مرورگر ریدایرکت به پنل."""
    if request.query_params.get("format") == "json":
        return True
    accept = (request.headers.get("accept") or "").lower()
    return "application/json" in accept and "text/html" not in accept


def _callback_finalize(request: Request, payload: dict[str, Any]) -> Response:
    """بازگشت JSON یا ریدایرکت ۳۰۲/۳۰۳ به پنل دانشجو."""
    if _callback_wants_json(request):
        return JSONResponse(content=payload)
    settings = get_settings()
    base = (settings.APP_BASE_URL or "").rstrip("/")
    path = getattr(settings, "PAYMENT_RETURN_PATH", "/panel/portal/student") or "/panel/portal/student"
    if not path.startswith("/"):
        path = "/" + path
    ok = payload.get("success") is True
    params: dict[str, str] = {"payment": "success" if ok else "failed"}
    if ok and payload.get("ref_id"):
        params["ref"] = str(payload.get("ref_id"))[:120]
    elif not ok:
        err = payload.get("error") or ""
        if err:
            params["reason"] = str(err)[:220]
    url = f"{base}{path}?{urlencode(params)}"
    code = 303 if request.method == "POST" else 302
    return RedirectResponse(url=url, status_code=code)


def _cb_str(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


async def _parse_callback_payload(request: Request) -> dict[str, Any]:
    """Merge query string (GET redirect) with body (POST form/json)."""
    data: dict[str, Any] = dict(request.query_params)
    try:
        content_type = request.headers.get("content-type", "")
        if "json" in content_type:
            raw = await request.json()
            if isinstance(raw, dict):
                data.update({str(k): raw[k] for k in raw})
            return data
        if request.method == "GET":
            return data
        form = await request.form()
        for k, v in form.multi_items():
            if hasattr(v, "read"):
                continue
            data[str(k)] = v
        return data
    except Exception:
        return data


async def _find_payment_pending(db: AsyncSession, data: dict[str, Any]) -> Optional[PaymentPending]:
    """Match by ResNum/orderId (authority), then gateway ref (token/trackId), then legacy authority-only rows."""
    res_num = _cb_str(
        data.get("ResNum")
        or data.get("resNum")
        or data.get("orderId")
        or data.get("orderid"),
    )
    ref_gate = _cb_str(
        data.get("RefNum")
        or data.get("refNum")
        or data.get("trackId")
        or data.get("trackid")
        or data.get("authority"),
    )
    if res_num:
        r = await db.execute(select(PaymentPending).where(PaymentPending.authority == res_num).limit(1))
        p = r.scalars().first()
        if p:
            return p
    if ref_gate:
        r = await db.execute(
            select(PaymentPending).where(PaymentPending.gateway_track_id == ref_gate).limit(1)
        )
        p = r.scalars().first()
        if p:
            return p
        r = await db.execute(select(PaymentPending).where(PaymentPending.authority == ref_gate).limit(1))
        p = r.scalars().first()
        if p:
            return p
    return None


def _callback_state_ok(data: dict[str, Any]) -> bool:
    state = _cb_str(data.get("State") or data.get("state"))
    status_code = data.get("Status")
    if state == "OK":
        return True
    if str(status_code) in ("0", "100"):
        return True
    if str(data.get("success", "")) == "1":
        return True
    return False


async def _handle_payment_callback(request: Request, db: AsyncSession) -> Response:
    data = await _parse_callback_payload(request)
    logger.info(f"[PAYMENT-CALLBACK] Received: {data}")

    ref_num = _cb_str(
        data.get("RefNum")
        or data.get("refNum")
        or data.get("trackId")
        or data.get("trackid")
        or data.get("authority"),
    )
    res_num = _cb_str(
        data.get("ResNum")
        or data.get("resNum")
        or data.get("orderId")
        or data.get("orderid"),
    )

    pending = await _find_payment_pending(db, data)

    raw_amt = data.get("Amount") or data.get("amount") or 0
    try:
        amount_rial = int(raw_amt) if raw_amt not in (None, "") else 0
    except (TypeError, ValueError):
        amount_rial = 0
    if amount_rial <= 0 and pending is not None:
        amount_rial = int(pending.amount)

    if _callback_state_ok(data):
        if not ref_num and pending and pending.gateway_track_id:
            ref_num = pending.gateway_track_id
        if not ref_num:
            logger.warning("[PAYMENT-CALLBACK] Success branch but no RefNum/trackId")
            await db.commit()
            return _callback_finalize(
                request,
                {"success": False, "error": "شناسه تراکنش درگاه یافت نشد"},
            )

        result = await verify_payment(str(ref_num), amount_rial)

        if result.success:
            student_id: Optional[uuid.UUID] = None
            if pending is not None:
                student_id = pending.student_id
            elif _is_uuid(res_num):
                student_id = uuid.UUID(res_num)

            amount_toman = amount_rial / 10.0
            if student_id is not None and amount_rial > 0:
                payment_svc = PaymentService(db)
                await payment_svc.record_payment(
                    student_id=student_id,
                    amount=amount_toman,
                    description=f"پرداخت موفق | ref={result.ref_id}",
                )

            if pending is not None:
                instance_id = pending.instance_id
                await _apply_payment_success_transition(
                    db,
                    instance_id,
                    pending,
                    amount_toman,
                    str(getattr(result, "ref_id", "") or ""),
                )
                await db.delete(pending)
            await db.commit()
            logger.info(f"[PAYMENT] Verified & recorded: ref={result.ref_id}")
            return _callback_finalize(
                request,
                {
                    "success": True,
                    "ref_id": result.ref_id,
                    "message": "پرداخت با موفقیت انجام شد",
                },
            )

        if pending is not None:
            await _fire_payment_unsuccessful(db, pending)
        await db.commit()
        return _callback_finalize(request, {"success": False, "error": result.error})

    logger.warning(
        f"[PAYMENT] Failed callback: state={data.get('State') or data.get('state')}, data_keys={list(data.keys())}"
    )
    if pending is not None:
        await _fire_payment_unsuccessful(db, pending)
    await db.commit()
    return _callback_finalize(request, {"success": False, "error": "پرداخت ناموفق بود"})


@router.post("/create")
async def create_payment_endpoint(
    req: CreatePaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a payment request and get redirect URL. If instance_id is set (e.g. session_payment), callback will run transition."""
    correlation_id = req.reference_id or str(uuid.uuid4().hex[:16])
    payment_req = PaymentRequest(
        amount=req.amount,
        description=req.description,
        student_id=req.student_id,
        reference_id=correlation_id,
        mobile=req.mobile,
    )
    result = await create_payment(payment_req)

    if result.success:
        if req.instance_id and _is_uuid(req.instance_id) and req.student_id and _is_uuid(req.student_id):
            pending = PaymentPending(
                id=uuid.uuid4(),
                authority=correlation_id,
                gateway_track_id=(result.authority or None),
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
            "reference_id": correlation_id,
        }
    else:
        raise HTTPException(status_code=400, detail=result.error)


@router.post("/callback")
async def payment_callback_post(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """POST callback (form/json) از درگاه؛ پیش‌فرض ریدایرکت به پنل (برای JSON پارامتر format=json)."""
    return await _handle_payment_callback(request, db)


@router.get("/callback")
async def payment_callback_get(
    request: Request, db: AsyncSession = Depends(get_db)
) -> Response:
    """GET callback؛ ریدایرکت به پنل دانشجو مگر format=json."""
    return await _handle_payment_callback(request, db)


@router.post("/verify")
async def verify_payment_endpoint(
    authority: str,
    amount: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually verify a payment (amount in Rials for SEP)."""
    result = await verify_payment(authority, amount)
    return result.to_dict()


def _is_uuid(val: str) -> bool:
    try:
        uuid.UUID(val)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


async def _get_system_actor_id(db: AsyncSession) -> uuid.UUID:
    """Return first admin user id for system-triggered transitions (e.g. payment callback)."""
    r = await db.execute(select(User.id).where(User.role == "admin").limit(1))
    row = r.scalars().first()
    if row is not None:
        return row
    r = await db.execute(select(User.id).limit(1))
    row = r.scalars().first()
    return row if row is not None else uuid.uuid4()


async def _apply_payment_success_transition(
    db: AsyncSession,
    instance_id: uuid.UUID,
    pending: PaymentPending,
    amount_toman: float,
    ref_id: str,
) -> bool:
    """پس از verify موفق درگاه: ترنزیشن مربوط به نمونهٔ پرداخت (session_payment یا start_therapy)."""
    r = await db.execute(select(ProcessInstance).where(ProcessInstance.id == instance_id))
    inst = r.scalars().first()
    if not inst or inst.is_completed or inst.is_cancelled:
        return False
    engine = StateMachineEngine(db)
    system_actor_id = await _get_system_actor_id(db)
    payload = {"amount": amount_toman, "ref_id": ref_id, "gateway_payment_ok": True}

    if inst.process_code == "session_payment" and inst.current_state_code == "awaiting_payment":
        try:
            await engine.execute_transition(
                instance_id=instance_id,
                trigger_event="payment_successful",
                actor_id=system_actor_id,
                actor_role="system",
                payload=payload,
            )
            logger.info(
                "[PAYMENT] session_payment_ok instance_id=%s student_id=%s amount_toman=%s ref=%s",
                instance_id,
                str(pending.student_id),
                amount_toman,
                ref_id,
            )
            return True
        except Exception as e:
            logger.exception(f"[PAYMENT] Transition payment_successful failed: {e}")
            return False

    if inst.process_code == "start_therapy" and inst.current_state_code == "payment_pending":
        try:
            await engine.execute_transition(
                instance_id=instance_id,
                trigger_event="payment_confirmed",
                actor_id=system_actor_id,
                actor_role="system",
                payload=payload,
            )
            logger.info(
                "[PAYMENT] start_therapy payment_confirmed instance_id=%s student_id=%s amount_toman=%s ref=%s",
                instance_id,
                str(pending.student_id),
                amount_toman,
                ref_id,
            )
            return True
        except Exception as e:
            logger.exception(f"[PAYMENT] Transition payment_confirmed failed for start_therapy: {e}")
            return False

    if inst.process_code == "extra_session" and inst.current_state_code == "payment_required":
        try:
            await engine.execute_transition(
                instance_id=instance_id,
                trigger_event="payment_completed",
                actor_id=system_actor_id,
                actor_role="system",
                payload=payload,
            )
            logger.info(
                "[PAYMENT] extra_session payment_completed instance_id=%s student_id=%s amount_toman=%s ref=%s",
                instance_id,
                str(pending.student_id),
                amount_toman,
                ref_id,
            )
            return True
        except Exception as e:
            logger.exception(f"[PAYMENT] Transition payment_completed failed for extra_session: {e}")
            return False

    return False


async def _fire_payment_unsuccessful(db: AsyncSession, pending: PaymentPending) -> None:
    """Run payment failure transition for session_payment یا start_therapy."""
    r = await db.execute(select(ProcessInstance).where(ProcessInstance.id == pending.instance_id))
    inst = r.scalars().first()
    if not inst or inst.is_completed:
        await db.delete(pending)
        return
    engine = StateMachineEngine(db)
    system_actor_id = await _get_system_actor_id(db)
    try:
        if inst.process_code == "session_payment" and inst.current_state_code == "awaiting_payment":
            await engine.execute_transition(
                instance_id=pending.instance_id,
                trigger_event="payment_unsuccessful",
                actor_id=system_actor_id,
                actor_role="system",
            )
            logger.info(
                "[PAYMENT] session_payment payment_unsuccessful instance %s",
                pending.instance_id,
            )
        elif inst.process_code == "start_therapy" and inst.current_state_code == "payment_pending":
            await engine.execute_transition(
                instance_id=pending.instance_id,
                trigger_event="payment_failed",
                actor_id=system_actor_id,
                actor_role="system",
            )
            logger.info(
                "[PAYMENT] start_therapy payment_failed instance %s",
                pending.instance_id,
            )
        elif inst.process_code == "extra_session" and inst.current_state_code == "payment_required":
            await engine.execute_transition(
                instance_id=pending.instance_id,
                trigger_event="payment_failed",
                actor_id=system_actor_id,
                actor_role="system",
            )
            logger.info(
                "[PAYMENT] extra_session payment_failed instance %s",
                pending.instance_id,
            )
    except Exception as e:
        logger.exception(f"[PAYMENT] Transition payment failure branch failed: {e}")
    await db.delete(pending)
