"""Payment API endpoints - create payment, handle callback, verify.

BUILD_TODO § و (بخش ۶): Callback drives session_payment via payment_successful/unsuccessful.
Amounts sent to Shaparak SEP are in Rials; internal ledger (FinancialRecord) uses Toman.
"""

import uuid
import logging
from typing import Any, Optional
from urllib.parse import urlencode

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.responses import JSONResponse, RedirectResponse, Response

from app.config import get_settings
from app.database import get_db
from app.api.auth import get_current_user
from app.models.operational_models import (
    User,
    ProcessInstance,
    PaymentPending,
    PaymentGatewayReceipt,
)
from app.services.payment_gateway import (
    PaymentRequest,
    create_payment,
    sep_pay_get_url,
    verify_payment,
)
from app.services.payment_service import PaymentService
from app.services.interview_slot_service import (
    clear_booking_deadline_for_instance,
    ensure_registration_interview_slot_has_alocom_link,
)
from app.services.alocom_provision import ensure_paid_session_alocom_links
from app.core.engine import StateMachineEngine
from app.core.audit import AuditLogger
from app.core.resource_access import ensure_can_pay_for_instance
from app.services.tuition_installment_service import (
    apply_post_payment_context_update,
    is_tuition_gateway_state,
    resolve_expected_payable_rial,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payment", tags=["Payment"])

# لاگ: بدون کارت/پان حساس
_CALLBACK_LOG_DENY = frozenset(
    {
        "SecurePan",
        "securePan",
        "cardNumber",
        "CardNumber",
        "card_pan",
        "hashedCardNumber",
    }
)


class CreatePaymentRequest(BaseModel):
    amount: int
    description: str = "پرداخت هزینه جلسه"
    student_id: Optional[str] = None
    reference_id: Optional[str] = None
    mobile: Optional[str] = None
    instance_id: Optional[str] = None  # session_payment instance for callback → transition
    # اختیاری: zibal | zarinpal | saman — اگر خالی باشد از PAYMENT_PROVIDER سرور استفاده می‌شود
    gateway: Optional[str] = None


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
        or data.get("authority")
        or data.get("Authority"),
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
    st = _cb_str(status_code)
    if st.upper() == "OK":
        return True
    if str(status_code) in ("0", "100"):
        return True
    if str(data.get("success", "")) == "1":
        return True
    return False


def _callback_payload_for_log(data: dict[str, Any]) -> dict[str, Any]:
    out = {k: ("***" if k in _CALLBACK_LOG_DENY else v) for k, v in data.items()}
    return out


def _payment_callback_success_path(
    data: dict[str, Any], pending: Optional[PaymentPending]
) -> bool:
    """زیبال: با `trackId` باید به verify رفت مگر `success=0` (لغو). سایر درگاه‌ها: State/Status کلاسیک."""
    prov = (pending.gateway_provider or "").lower() if pending else ""
    if prov == "zibal" and _cb_str(data.get("trackId") or data.get("trackid")):
        s = str(data.get("success", "")).strip().lower()
        if s in ("0", "false"):
            return False
        return True
    return _callback_state_ok(data)


async def _gateway_receipt_exists(
    db: AsyncSession, provider: str, gateway_ref: str
) -> bool:
    if not gateway_ref or not provider:
        return False
    r = await db.execute(
        select(PaymentGatewayReceipt.id).where(
            PaymentGatewayReceipt.provider == provider,
            PaymentGatewayReceipt.gateway_ref == gateway_ref[:128],
        ).limit(1)
    )
    return r.scalars().first() is not None


async def _insert_gateway_receipt(
    db: AsyncSession,
    *,
    provider: str,
    gateway_ref: str,
    authority: str | None,
    amount_rial: int,
    student_id: uuid.UUID | None,
    process_instance_id: uuid.UUID | None,
) -> bool:
    """Insert receipt; return False if duplicate (idempotent callback)."""
    if not gateway_ref:
        return True
    db.add(
        PaymentGatewayReceipt(
            id=uuid.uuid4(),
            provider=provider[:32],
            gateway_ref=gateway_ref[:128],
            authority=authority,
            amount_rial=int(amount_rial),
            student_id=student_id,
            process_instance_id=process_instance_id,
        )
    )
    try:
        async with db.begin_nested():
            await db.flush()
        return True
    except IntegrityError:
        return False


async def _handle_payment_callback(request: Request, db: AsyncSession) -> Response:
    data = await _parse_callback_payload(request)
    logger.info(f"[PAYMENT-CALLBACK] keys={list(data.keys())} safe={_callback_payload_for_log(data)}")

    ref_num = _cb_str(
        data.get("RefNum")
        or data.get("refNum")
        or data.get("trackId")
        or data.get("trackid")
        or data.get("authority")
        or data.get("Authority"),
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

    if _payment_callback_success_path(data, pending):
        if not ref_num and pending and pending.gateway_track_id:
            gprov = (pending.gateway_provider or "").lower()
            if gprov in ("zibal", "zarinpal", "mock", ""):
                ref_num = pending.gateway_track_id
        if not ref_num:
            logger.warning("[PAYMENT-CALLBACK] Success branch but no RefNum/trackId")
            await db.commit()
            return _callback_finalize(
                request,
                {"success": False, "error": "شناسه تراکنش درگاه یافت نشد"},
            )

        verify_kw: dict[str, Any] = {}
        if pending is not None and getattr(pending, "gateway_provider", None):
            verify_kw["provider"] = pending.gateway_provider
        result = await verify_payment(str(ref_num), amount_rial, **verify_kw)

        if result.success:
            vprov = (verify_kw.get("provider") or get_settings().PAYMENT_PROVIDER or "mock").strip().lower() or "mock"
            gref = str(getattr(result, "ref_id", "") or ref_num or "")
            amount_toman = amount_rial / 10.0
            audit = AuditLogger(db)

            student_id: Optional[uuid.UUID] = None
            if pending is not None:
                student_id = pending.student_id
            elif _is_uuid(res_num):
                student_id = uuid.UUID(res_num)

            if gref and await _gateway_receipt_exists(db, vprov, gref):
                transition_ok = False
                if pending is not None:
                    transition_ok = await _apply_payment_success_transition(
                        db,
                        pending.instance_id,
                        pending,
                        amount_toman,
                        gref,
                    )
                    if transition_ok:
                        await db.delete(pending)
                await audit.log(
                    action_type="payment_callback_idempotent",
                    instance_id=pending.instance_id if pending else None,
                    details={"provider": vprov, "ref": gref, "transition_ok": transition_ok},
                )
                await db.commit()
                logger.info("[PAYMENT] idempotent callback ref=%s provider=%s", gref, vprov)
                return _callback_finalize(
                    request,
                    {
                        "success": True,
                        "ref_id": gref,
                        "message": "پرداخت قبلاً ثبت شده",
                    },
                )

            receipt_inserted = True
            if gref and pending is not None:
                receipt_inserted = await _insert_gateway_receipt(
                    db,
                    provider=vprov,
                    gateway_ref=gref,
                    authority=pending.authority,
                    amount_rial=int(amount_rial),
                    student_id=student_id,
                    process_instance_id=pending.instance_id,
                )
                if not receipt_inserted:
                    transition_ok = await _apply_payment_success_transition(
                        db,
                        pending.instance_id,
                        pending,
                        amount_toman,
                        gref,
                    )
                    if transition_ok:
                        await db.delete(pending)
                    await db.commit()
                    return _callback_finalize(
                        request,
                        {"success": True, "ref_id": gref, "message": "پرداخت قبلاً ثبت شده"},
                    )

            transition_ok = False
            if pending is not None:
                transition_ok = await _apply_payment_success_transition(
                    db,
                    pending.instance_id,
                    pending,
                    amount_toman,
                    gref,
                )

            if not transition_ok:
                await audit.log(
                    action_type="payment_transition_failed",
                    instance_id=pending.instance_id if pending else None,
                    details={
                        "provider": vprov,
                        "ref": gref,
                        "amount_rial": amount_rial,
                        "pending_kept": pending is not None,
                    },
                )
                await db.commit()
                logger.error(
                    "[PAYMENT] Verified at gateway but workflow transition failed ref=%s instance=%s",
                    gref,
                    pending.instance_id if pending else None,
                )
                return _callback_finalize(
                    request,
                    {
                        "success": False,
                        "error": "پرداخت در درگاه تأیید شد اما به‌روزرسانی فرایند ناموفق بود. با پشتیبانی تماس بگیرید.",
                        "ref_id": gref,
                    },
                )

            if student_id is not None and amount_rial > 0 and pending is not None:
                payment_svc = PaymentService(db)
                await payment_svc.record_payment(
                    student_id=student_id,
                    amount=amount_toman,
                    description=f"پرداخت موفق | ref={gref or ref_num}",
                )
                await db.delete(pending)

            await audit.log(
                action_type="payment_success",
                instance_id=pending.instance_id if pending else None,
                details={"provider": vprov, "ref": gref, "amount_toman": amount_toman},
            )
            await db.commit()
            logger.info("[PAYMENT] Verified & recorded: ref=%s", result.ref_id)
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


def _payment_success_return_url(ref_id: str = "") -> str:
    """آدرس بازگشت موفقِ پنل برای حالت بای‌پس تست.

    این مسیر را فرانت‌اند با `window.location.assign` باز می‌کند، پس عمداً
    «نسبی» برمی‌گردد (بدون APP_BASE_URL) تا روی همان origin فعلی (مثلاً
    localhost در تست) باز شود؛ resolvePaymentUrl سمت کلاینت origin/base را
    اضافه می‌کند. اگر APP_BASE_URL مطلقِ پروداکشن را اینجا می‌گذاشتیم، تست
    محلی به دامنهٔ پروداکشن پرت می‌شد.
    """
    settings = get_settings()
    path = getattr(settings, "PAYMENT_RETURN_PATH", "/panel/portal/student") or "/panel/portal/student"
    if not path.startswith("/"):
        path = "/" + path
    params: dict[str, str] = {"payment": "success", "bypass": "1"}
    if ref_id:
        params["ref"] = str(ref_id)[:120]
    return f"{path}?{urlencode(params)}"


async def _bypass_payment_success(
    db: AsyncSession,
    req: CreatePaymentRequest,
    correlation_id: str,
) -> dict[str, Any]:
    """حالت تست: درگاه واقعی دور زده می‌شود و پرداخت بلافاصله موفق ثبت می‌شود.

    همان ترنزیشن‌های موفقیت و ثبت سند مالیِ مسیر کال‌بک واقعی اجرا می‌شوند تا
    جریان فرایند در سامانه دقیقاً مثل پرداخت واقعی پیش برود. با False کردن
    PAYMENT_TEST_BYPASS این مسیر کامل غیرفعال شده و درگاه واقعی برمی‌گردد.
    """
    ref_id = f"BYPASS-{uuid.uuid4().hex[:12]}"
    amount_rial = int(req.amount or 0)
    amount_toman = amount_rial / 10.0

    if (
        req.instance_id
        and _is_uuid(req.instance_id)
        and req.student_id
        and _is_uuid(req.student_id)
    ):
        student_id = uuid.UUID(req.student_id)
        instance_id = uuid.UUID(req.instance_id)
        pending = PaymentPending(
            id=uuid.uuid4(),
            authority=correlation_id,
            gateway_track_id=ref_id,
            gateway_provider="bypass",
            instance_id=instance_id,
            student_id=student_id,
            amount=amount_rial,
        )
        db.add(pending)
        await db.flush()

        transition_ok = await _apply_payment_success_transition(
            db,
            instance_id,
            pending,
            amount_toman,
            ref_id,
        )
        if transition_ok:
            if amount_rial > 0:
                payment_svc = PaymentService(db)
                await payment_svc.record_payment(
                    student_id=student_id,
                    amount=amount_toman,
                    description=f"پرداخت تستی (بای‌پس درگاه) | ref={ref_id}",
                )
            await db.delete(pending)

    await db.commit()
    logger.warning(
        "[PAYMENT-BYPASS] حالت تست فعال است؛ پرداخت بدون درگاه موفق ثبت شد ref=%s instance=%s amount_rial=%s",
        ref_id,
        req.instance_id,
        amount_rial,
    )
    return {
        "success": True,
        "payment_url": _payment_success_return_url(ref_id),
        "authority": ref_id,
        "reference_id": correlation_id,
        "bypass": True,
    }


def _effective_payment_provider(req: CreatePaymentRequest) -> str:
    settings = get_settings()
    base = (settings.PAYMENT_PROVIDER or "mock").strip().lower() or "mock"
    zibal_only = getattr(settings, "PAYMENT_ZIBAL_ONLY", False)
    if zibal_only and base in ("saman", "zarinpal"):
        base = "zibal"
    if req.gateway:
        g = req.gateway.strip().lower()
        if g not in ("zibal", "zarinpal", "saman", "mock"):
            raise HTTPException(
                status_code=400,
                detail="gateway باید zibal، zarinpal، saman یا mock باشد",
            )
        if zibal_only and g not in ("zibal", "mock"):
            raise HTTPException(
                status_code=400,
                detail="فعلاً فقط درگاه زیبال فعال است.",
            )
        return g
    return base


def _sep_fallback_allowed(settings) -> bool:
    if getattr(settings, "PAYMENT_ZIBAL_ONLY", False):
        return False
    return bool((getattr(settings, "SEP_TERMINAL_ID", "") or "").strip())


def _should_try_sep_after_zibal(requested_provider: str, settings) -> bool:
    """After a failed Zibal create, try SEP once (primary=zibal, backup=saman)."""
    return (requested_provider or "").strip().lower() == "zibal" and _sep_fallback_allowed(settings)


@router.get("/sep/start")
async def sep_start_redirect(token: str = "") -> Response:
    """302 to official SEP GET URL. Kept for old bookmarks; create() no longer uses this hop."""
    tok = (token or "").strip()
    if not tok or len(tok) > 256:
        raise HTTPException(status_code=400, detail="توکن سپ نامعتبر است")
    return RedirectResponse(url=sep_pay_get_url(tok), status_code=302)


@router.post("/create")
async def create_payment_endpoint(
    req: CreatePaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a payment request and get redirect URL. If instance_id is set (e.g. session_payment), callback will run transition."""
    correlation_id = req.reference_id or str(uuid.uuid4().hex[:16])

    settings = get_settings()
    if settings.PAYMENT_TEST_BYPASS:
        if not settings.DEBUG:
            raise HTTPException(status_code=403, detail="PAYMENT_TEST_BYPASS is disabled in production")
        return await _bypass_payment_success(db, req, correlation_id)

    if req.student_id and _is_uuid(req.student_id):
        sid = uuid.UUID(req.student_id)
        iid = uuid.UUID(req.instance_id) if req.instance_id and _is_uuid(req.instance_id) else None
        await ensure_can_pay_for_instance(db, current_user, sid, iid)

        if iid is not None:
            inst_row = await db.execute(select(ProcessInstance).where(ProcessInstance.id == iid))
            inst = inst_row.scalars().first()
            if inst and is_tuition_gateway_state(inst.process_code, inst.current_state_code or ""):
                expected = await resolve_expected_payable_rial(db, inst)
                if expected is not None and int(req.amount) != int(expected):
                    raise HTTPException(
                        status_code=400,
                        detail=(
                            f"مبلغ پرداخت ({int(req.amount):,} ریال) با مبلغ قابل‌پرداخت "
                            f"({int(expected):,} ریال) مطابقت ندارد. صفحه را تازه کنید."
                        ),
                    )

    effective_provider = _effective_payment_provider(req)
    payment_req = PaymentRequest(
        amount=req.amount,
        description=req.description,
        student_id=req.student_id,
        reference_id=correlation_id,
        mobile=req.mobile,
        provider=effective_provider,
    )
    result = await create_payment(payment_req)
    used_provider = effective_provider
    fallback_from = None
    if (
        not result.success
        and _should_try_sep_after_zibal(effective_provider, settings)
    ):
        logger.warning(
            "[PAYMENT] Zibal create failed (%s); falling back to SEP",
            result.error,
        )
        payment_req.provider = "saman"
        result = await create_payment(payment_req)
        if result.success:
            used_provider = "saman"
            fallback_from = "zibal"

    if result.success:
        if req.instance_id and _is_uuid(req.instance_id) and req.student_id and _is_uuid(req.student_id):
            pending = PaymentPending(
                id=uuid.uuid4(),
                authority=correlation_id,
                gateway_track_id=(result.authority or None),
                gateway_provider=used_provider,
                instance_id=uuid.UUID(req.instance_id),
                student_id=uuid.UUID(req.student_id),
                amount=req.amount,
            )
            db.add(pending)
            await db.flush()
        payload = {
            "success": True,
            "payment_url": result.payment_url,
            "authority": result.authority,
            "reference_id": correlation_id,
            "provider": used_provider,
        }
        if fallback_from:
            payload["fallback_from"] = fallback_from
        return payload
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
    provider: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Manually verify a payment (amount in Rials for SEP). Operators only."""
    from app.core.resource_access import is_operator_role

    if not is_operator_role(current_user.role):
        raise HTTPException(status_code=403, detail="Manual payment verify requires operator role")
    result = await verify_payment(authority, amount, provider=provider)
    audit = AuditLogger(db)
    await audit.log(
        action_type="payment_manual_verify",
        actor_id=current_user.id,
        actor_role=current_user.role,
        details={"authority": authority[:64], "success": result.success},
    )
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
            try:
                links = await ensure_paid_session_alocom_links(
                    db, student_id=pending.student_id
                )
                if links:
                    logger.info(
                        "[PAYMENT] session_payment alocom links provisioned student_id=%s count=%s",
                        str(pending.student_id),
                        len(links),
                    )
            except Exception:
                logger.exception(
                    "[PAYMENT] session_payment alocom link provisioning failed student_id=%s",
                    str(pending.student_id),
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
            try:
                links = await ensure_paid_session_alocom_links(
                    db, student_id=pending.student_id
                )
                if links:
                    logger.info(
                        "[PAYMENT] start_therapy alocom links provisioned student_id=%s count=%s",
                        str(pending.student_id),
                        len(links),
                    )
            except Exception:
                logger.exception(
                    "[PAYMENT] start_therapy alocom link provisioning failed student_id=%s",
                    str(pending.student_id),
                )
            return True
        except Exception as e:
            logger.exception(f"[PAYMENT] Transition payment_confirmed failed for start_therapy: {e}")
            return False

    if inst.process_code == "return_to_full_education":
        if inst.current_state_code == "therapy_payment_pending":
            try:
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="therapy_payment_confirmed",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] return_to_full_education therapy_payment_confirmed instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception(
                    "[PAYMENT] return_to_full_education therapy_payment_confirmed failed: %s", e,
                )
                return False
        if inst.current_state_code == "supervision_payment_pending":
            try:
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="supervision_payment_confirmed",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] return_to_full_education supervision_payment_confirmed instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception(
                    "[PAYMENT] return_to_full_education supervision_payment_confirmed failed: %s", e,
                )
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

    if inst.process_code == "introductory_course_registration":
        if inst.current_state_code == "interview_payment":
            try:
                # مهلت پرداخت باید قبل از ساخت لینک الوکام پاک شود؛ در غیر این صورت
                # maybe_provision_interview_slot_alocom_link و قوانین نمایش لینک آن را مسدود می‌کنند.
                await clear_booking_deadline_for_instance(db, instance_id)
                await ensure_registration_interview_slot_has_alocom_link(db, instance_id=instance_id)
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="payment_success",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] intro_reg interview payment_success instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception("[PAYMENT] intro_reg payment_success failed: %s", e)
                return False
        if inst.current_state_code == "payment":
            try:
                await apply_post_payment_context_update(
                    db, inst, payment_ref=ref_id, amount_rial=int(round(amount_toman * 10))
                )
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="payment_completed",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] intro_reg tuition payment_completed instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception("[PAYMENT] intro_reg payment_completed failed: %s", e)
                return False

    if inst.process_code == "comprehensive_course_registration":
        if inst.current_state_code == "interview_payment":
            try:
                await clear_booking_deadline_for_instance(db, instance_id)
                await ensure_registration_interview_slot_has_alocom_link(db, instance_id=instance_id)
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="interview_payment_confirmed",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] comp_reg interview interview_payment_confirmed instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception("[PAYMENT] comp_reg interview_payment_confirmed failed: %s", e)
                return False
        if inst.current_state_code == "payment":
            try:
                await apply_post_payment_context_update(
                    db, inst, payment_ref=ref_id, amount_rial=int(round(amount_toman * 10))
                )
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="tuition_payment_confirmed",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] comp_reg tuition tuition_payment_confirmed instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception("[PAYMENT] comp_reg tuition_payment_confirmed failed: %s", e)
                return False

    if inst.process_code == "comprehensive_term_start":
        if inst.current_state_code == "payment_processing":
            try:
                await apply_post_payment_context_update(
                    db, inst, payment_ref=ref_id, amount_rial=int(round(amount_toman * 10))
                )
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="payment_confirmed",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] comp_term_start payment_confirmed instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception("[PAYMENT] comp_term_start payment_confirmed failed: %s", e)
                return False

    if inst.process_code == "supervision_block_transition":
        if inst.current_state_code == "slot_selected":
            try:
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="payment_success_new_block_first",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] supervision_block_transition payment_success_new_block_first instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception(
                    "[PAYMENT] supervision_block_transition payment_success_new_block_first failed: %s",
                    e,
                )
                return False
        if inst.current_state_code == "new_block_first_paid":
            try:
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="payment_success_50th",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] supervision_block_transition payment_success_50th instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception(
                    "[PAYMENT] supervision_block_transition payment_success_50th failed: %s",
                    e,
                )
                return False

    if inst.process_code == "intro_second_semester_registration":
        if inst.current_state_code == "payment_processing":
            try:
                await apply_post_payment_context_update(
                    db, inst, payment_ref=ref_id, amount_rial=int(round(amount_toman * 10))
                )
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="payment_completed",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] intro_term2 payment_completed instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception("[PAYMENT] intro_term2 payment_completed failed: %s", e)
                return False
        if inst.current_state_code == "installment_overdue":
            try:
                await apply_post_payment_context_update(
                    db, inst, payment_ref=ref_id, amount_rial=int(round(amount_toman * 10))
                )
                await engine.execute_transition(
                    instance_id=instance_id,
                    trigger_event="overdue_installment_paid",
                    actor_id=system_actor_id,
                    actor_role="system",
                    payload=payload,
                )
                logger.info(
                    "[PAYMENT] intro_term2 overdue_installment_paid instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True
            except Exception as e:
                logger.exception("[PAYMENT] intro_term2 overdue_installment_paid failed: %s", e)
                return False
        if inst.current_state_code == "registration_complete":
            ctx = dict(inst.context_data or {})
            try:
                pending = int(ctx.get("pending_installments_remaining") or 0)
            except (TypeError, ValueError):
                pending = 0
            if pending > 0 and ctx.get("payment_method") == "installment":
                await apply_post_payment_context_update(
                    db, inst, payment_ref=ref_id, amount_rial=int(round(amount_toman * 10))
                )
                logger.info(
                    "[PAYMENT] intro_term2 installment paid (registration_complete) instance_id=%s ref=%s",
                    instance_id,
                    ref_id,
                )
                return True

    if inst.process_code in (
        "introductory_course_registration",
        "comprehensive_course_registration",
        "comprehensive_term_start",
    ) and inst.current_state_code == "installment_overdue":
        try:
            await apply_post_payment_context_update(
                db, inst, payment_ref=ref_id, amount_rial=int(round(amount_toman * 10))
            )
            await engine.execute_transition(
                instance_id=instance_id,
                trigger_event="overdue_installment_paid",
                actor_id=system_actor_id,
                actor_role="system",
                payload=payload,
            )
            logger.info(
                "[PAYMENT] %s overdue_installment_paid instance_id=%s ref=%s",
                inst.process_code,
                instance_id,
                ref_id,
            )
            return True
        except Exception as e:
            logger.exception("[PAYMENT] overdue_installment_paid failed: %s", e)
            return False

    if inst.process_code in (
        "introductory_course_registration",
        "comprehensive_course_registration",
        "comprehensive_term_start",
    ) and inst.current_state_code == "registration_complete":
        ctx = dict(inst.context_data or {})
        try:
            pending = int(ctx.get("pending_installments_remaining") or 0)
        except (TypeError, ValueError):
            pending = 0
        if pending > 0 and ctx.get("payment_method") == "installment":
            await apply_post_payment_context_update(
                db, inst, payment_ref=ref_id, amount_rial=int(round(amount_toman * 10))
            )
            logger.info(
                "[PAYMENT] %s installment paid (registration_complete) instance_id=%s ref=%s",
                inst.process_code,
                instance_id,
                ref_id,
            )
            return True

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
        elif (
            inst.process_code == "introductory_course_registration"
            and inst.current_state_code == "interview_payment"
        ):
            await engine.execute_transition(
                instance_id=pending.instance_id,
                trigger_event="payment_failed",
                actor_id=system_actor_id,
                actor_role="system",
            )
            logger.info(
                "[PAYMENT] intro_reg interview payment_failed instance %s",
                pending.instance_id,
            )
        elif inst.process_code == "introductory_course_registration" and inst.current_state_code == "payment":
            await engine.execute_transition(
                instance_id=pending.instance_id,
                trigger_event="payment_failed",
                actor_id=system_actor_id,
                actor_role="system",
            )
            logger.info(
                "[PAYMENT] intro_reg tuition payment_failed instance %s",
                pending.instance_id,
            )
        elif (
            inst.process_code == "comprehensive_course_registration"
            and inst.current_state_code == "interview_payment"
        ):
            await engine.execute_transition(
                instance_id=pending.instance_id,
                trigger_event="interview_payment_failed",
                actor_id=system_actor_id,
                actor_role="system",
            )
            logger.info(
                "[PAYMENT] comp_reg interview_payment_failed instance %s",
                pending.instance_id,
            )
        elif inst.process_code == "comprehensive_course_registration" and inst.current_state_code == "payment":
            await engine.execute_transition(
                instance_id=pending.instance_id,
                trigger_event="tuition_payment_failed",
                actor_id=system_actor_id,
                actor_role="system",
            )
            logger.info(
                "[PAYMENT] comp_reg tuition_payment_failed instance %s",
                pending.instance_id,
            )
    except Exception as e:
        logger.exception(f"[PAYMENT] Transition payment failure branch failed: {e}")
    await db.delete(pending)
