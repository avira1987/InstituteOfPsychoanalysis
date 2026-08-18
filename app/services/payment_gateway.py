"""Payment Gateway - Pluggable payment processing.

Providers:
  - "mock"     → development (always succeeds)
  - "saman"    → Saman (SEP) via sep.shaparak.ir (amounts in Rials)
  - "zibal"    → Zibal via gateway.zibal.ir
  - "zarinpal" → Zarinpal REST v4 (api.zarinpal.com)

Configure via .env (never commit real secrets):
  PAYMENT_PROVIDER=saman
  SEP_TERMINAL_ID=<terminal_id>
  SEP_PASSWORD=<optional per merchant doc>
  PAYMENT_CALLBACK_URL=https://yourdomain.com/api/payment/callback

  # Zibal:
  PAYMENT_PROVIDER=zibal
  ZIBAL_MERCHANT=your_merchant_id

  # Zarinpal:
  PAYMENT_PROVIDER=zarinpal
  ZARINPAL_MERCHANT_ID=<merchant_uuid>
  ZARINPAL_SANDBOX=false
"""

import uuid
import logging
from typing import Optional
from app.config import effective_payment_callback_url, get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PaymentRequest:
    def __init__(self, amount: int, description: str, callback_url: str = "",
                 student_id: Optional[str] = None, reference_id: Optional[str] = None,
                 mobile: Optional[str] = None, provider: Optional[str] = None):
        self.amount = amount
        self.description = description
        self.callback_url = (callback_url or effective_payment_callback_url()).strip()
        self.student_id = student_id
        self.reference_id = reference_id
        self.mobile = mobile
        self.provider = (provider or "").strip().lower() or None


class PaymentResponse:
    def __init__(self, success: bool, authority: str = "", payment_url: str = "",
                 ref_id: str = "", error: str = ""):
        self.success = success
        self.authority = authority
        self.payment_url = payment_url
        self.ref_id = ref_id
        self.error = error

    def to_dict(self):
        return {
            "success": self.success,
            "authority": self.authority,
            "payment_url": self.payment_url,
            "ref_id": self.ref_id,
            "error": self.error,
        }


# ─── Public API ──────────────────────────────────────────────────

def _resolve_provider(request_or_override: Optional[str]) -> str:
    p = (request_or_override or settings.PAYMENT_PROVIDER or "mock").strip().lower()
    return p if p else "mock"


async def create_payment(request: PaymentRequest) -> PaymentResponse:
    provider = _resolve_provider(request.provider)
    if provider == "saman":
        return await _saman_create(request)
    elif provider == "zibal":
        return await _zibal_create(request)
    elif provider == "zarinpal":
        return await _zarinpal_create(request)
    else:
        return _mock_create(request)


async def verify_payment(authority: str, amount: int, provider: Optional[str] = None) -> PaymentResponse:
    p = _resolve_provider(provider)
    if p == "saman":
        return await _saman_verify(authority, amount)
    elif p == "zibal":
        return await _zibal_verify(authority, amount)
    elif p == "zarinpal":
        return await _zarinpal_verify(authority, amount)
    else:
        if settings.DEBUG:
            return _mock_verify(authority, amount)
        return PaymentResponse(success=False, error="Payment provider not configured")


# ─── Mock ────────────────────────────────────────────────────────

def _mock_create(request: PaymentRequest) -> PaymentResponse:
    authority = f"MOCK-{uuid.uuid4().hex[:12]}"
    logger.info(f"[PAYMENT-MOCK] Created: amount={request.amount}, authority={authority}")
    return PaymentResponse(success=True, authority=authority,
                           payment_url=f"/payment/mock/{authority}", ref_id=authority)


def _mock_verify(authority: str, amount: int) -> PaymentResponse:
    logger.info(f"[PAYMENT-MOCK] Verified: authority={authority}, amount={amount}")
    return PaymentResponse(success=True, authority=authority, ref_id=f"REF-{authority}")


# ─── Saman (SEP) ────────────────────────────────────────────────

SEP_TOKEN_URLS = (
    "https://sep.shaparak.ir/onlinepg/onlinepg",
    "https://sep.shaparak.ir/OnlinePG/SendToken",
)
SEP_PAY_POST_URL = "https://sep.shaparak.ir/OnlinePG/OnlinePG"
SEP_PAY_GET_URL = "https://sep.shaparak.ir/OnlinePG/SendToken"


def normalize_sep_cell_number(mobile: Optional[str]) -> str:
    """SEP sample uses 10 digits without leading 0 (9120000000)."""
    digits = "".join(c for c in (mobile or "") if c.isdigit())
    if digits.startswith("98") and len(digits) >= 12:
        digits = digits[2:]
    if digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) == 10 and digits.startswith("9"):
        return digits
    return ""


def sep_pay_get_url(token: str) -> str:
    """Official GET redirect (merchant doc 3.3 / SEP SDKs). Do not use OnlinePG?Token=."""
    from urllib.parse import quote

    tok = str(token or "").strip()
    return f"{SEP_PAY_GET_URL}?token={quote(tok, safe='')}"


def sep_browser_start_url(token: str) -> str:
    """Send the browser straight to SEP. An extra hop on our domain often drops the token
    (query string stripped by proxy, APP_BASE_URL pointing at another host) →
    «توکن ارسالی یافت نشد».
    """
    return sep_pay_get_url(token)


def _sep_token_payload(request: PaymentRequest, terminal_id: str) -> dict:
    payload = {
        "action": "token",
        "TerminalId": str(terminal_id).strip(),
        "Amount": int(request.amount),
        "ResNum": request.reference_id or str(uuid.uuid4().hex[:16]),
        "RedirectUrl": request.callback_url,
    }
    cell = normalize_sep_cell_number(request.mobile)
    if cell:
        payload["CellNumber"] = cell
    return payload


async def _saman_create(request: PaymentRequest) -> PaymentResponse:
    """Saman SEP: GetToken then redirect to payment page.

    Official flow (merchant doc 3.3):
    1. POST JSON to /onlinepg/onlinepg → token
    2. Browser POST Token to /OnlinePG/OnlinePG (or GET /OnlinePG/SendToken?token=)
    3. User pays, redirected to RedirectUrl
    4. Verify via /verifyTxnRandomSessionkey/ipg/VerifyTransaction
    """
    terminal_id = (settings.SEP_TERMINAL_ID or "").strip()
    if not terminal_id:
        if settings.DEBUG:
            logger.warning("SEP_TERMINAL_ID not set, falling back to mock (DEBUG only)")
            return _mock_create(request)
        return PaymentResponse(success=False, error="SEP_TERMINAL_ID is not configured")

    try:
        import httpx

        payload = _sep_token_payload(request, terminal_id)
        last_error = "پاسخ نامعتبر از سپ"
        async with httpx.AsyncClient(timeout=20) as client:
            for token_url in SEP_TOKEN_URLS:
                resp = await client.post(token_url, json=payload)
                try:
                    data = resp.json()
                except Exception:
                    body = (resp.text or "")[:800]
                    logger.error(
                        "[SEP] Non-JSON from %s: status=%s body=%r",
                        token_url,
                        resp.status_code,
                        body,
                    )
                    last_error = f"پاسخ غیرمنتظره از سپ (کد {resp.status_code})"
                    continue

                status = data.get("status")
                token = str(data.get("token") or data.get("Token") or "").strip()
                ok = bool(token) and (status == 1 or str(status) == "1")
                if ok:
                    payment_url = sep_browser_start_url(token)
                    logger.info(
                        "[SEP] Token obtained via %s callback=%s amount=%s",
                        token_url,
                        request.callback_url,
                        payload.get("Amount"),
                    )
                    return PaymentResponse(success=True, authority=token, payment_url=payment_url)

                error_msg = data.get("errorDesc") or data.get("errorCode") or f"status={status}"
                logger.error("[SEP] Token error from %s: %s data=%s", token_url, error_msg, data)
                last_error = str(error_msg)
                if status == -1:
                    break

        return PaymentResponse(success=False, error=str(last_error))

    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return PaymentResponse(success=False, error="httpx not installed")
    except Exception as e:
        logger.error(f"[SEP] Exception: {e}")
        return PaymentResponse(success=False, error=str(e))


async def _saman_verify(ref_num: str, amount: int) -> PaymentResponse:
    """Saman SEP: VerifyTransaction after callback."""
    terminal_id = settings.SEP_TERMINAL_ID
    if not terminal_id:
        if settings.DEBUG:
            return _mock_verify(ref_num, amount)
        return PaymentResponse(success=False, error="SEP_TERMINAL_ID is not configured")

    try:
        import httpx
        verify_url = "https://sep.shaparak.ir/verifyTxnRandomSessionkey/ipg/VerifyTransaction"

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(verify_url, json={
                "RefNum": ref_num,
                "TerminalNumber": int(terminal_id),
            })
            data = resp.json()

            transaction_detail = data.get("TransactionDetail", {})
            result_code = data.get("ResultCode")
            success = data.get("Success", False)

            if success and result_code == 0:
                verified_amount = transaction_detail.get("OrginalAmount", 0)
                if verified_amount == amount:
                    rrn = str(transaction_detail.get("RRN", ""))
                    logger.info(f"[SEP] Verified: RefNum={ref_num}, RRN={rrn}")
                    return PaymentResponse(success=True, authority=ref_num, ref_id=rrn)
                else:
                    logger.error(f"[SEP] Amount mismatch: expected={amount}, got={verified_amount}")
                    return PaymentResponse(success=False, authority=ref_num,
                                           error=f"Amount mismatch: {verified_amount} != {amount}")
            else:
                error_desc = data.get("ResultDescription", f"ResultCode={result_code}")
                logger.error(f"[SEP] Verify failed: {error_desc}")
                return PaymentResponse(success=False, authority=ref_num, error=error_desc)

    except Exception as e:
        logger.error(f"[SEP] Verify exception: {e}")
        return PaymentResponse(success=False, authority=ref_num, error=str(e))


# ─── Zibal ───────────────────────────────────────────────────────

def _zibal_base_url() -> str:
    """همیشه host اصلی IPG؛ حالت تست با فیلد sandbox در JSON (نه زیردامنه sandbox که اغلب timeout/مسدود است)."""
    return "https://gateway.zibal.ir"


def _zibal_humanize_error(raw: str) -> str:
    """پیام‌های رایج API زیبال به متن قابل‌فهم برای اپراتور."""
    if not raw or not str(raw).strip():
        return "خطای نامشخص از درگاه زیبال"
    s = str(raw).strip()
    low = s.lower()
    if "invalid ip" in low:
        return (
            "IP سروری که بک‌اند روی آن به اینترنت وصل است در پنل زیبال مجاز نیست. "
            "در my.zibal.ir → تنظیمات / محدودیت IP، IP عمومی همین سرور را اضافه کنید "
            "(همان IPای که زیبال در خطا نشان می‌دهد). تا آن زمان پرداخت از سرور رد می‌شود. "
            f"[%s]" % s
        )
    if "invalid merchant" in low or "result=104" in low:
        return (
            "کد مرچنت (ZIBAL_MERCHANT) در زیبال شناخته نشد یا برای این محیط فعال نیست؛ "
            "در my.zibal.ir مرچنت و حالت سندباکس/واقعی را چک کنید. "
            f"[%s]" % s
        )
    return s


async def _zibal_create(request: PaymentRequest) -> PaymentResponse:
    """Zibal: POST to /v1/request → get trackId → redirect."""
    merchant = settings.ZIBAL_MERCHANT
    if not merchant:
        logger.warning("ZIBAL_MERCHANT not set")
        return PaymentResponse(
            success=False,
            error="درگاه زیبال روی سرور تنظیم نشده؛ متغیر ZIBAL_MERCHANT را در محیط اجرا قرار دهید.",
        )

    base = _zibal_base_url()
    is_sandbox = bool(getattr(settings, "ZIBAL_SANDBOX", False))

    try:
        import httpx
        url = f"{base}/v1/request"

        async with httpx.AsyncClient(timeout=15) as client:
            payload = {
                "merchant": merchant,
                "amount": request.amount,
                "callbackUrl": request.callback_url,
                "description": request.description,
                "orderId": request.reference_id or "",
                "mobile": request.mobile or "",
            }
            if is_sandbox:
                payload["sandbox"] = True
            resp = await client.post(url, json=payload)
            if resp.status_code and resp.status_code >= 400:
                body = (resp.text or "")[:500]
                logger.error(f"[ZIBAL] request HTTP {resp.status_code}: {body!r}")
                return PaymentResponse(
                    success=False,
                    error=f"خطای ارتباط با درگاه (HTTP {resp.status_code})",
                )
            try:
                data = resp.json()
            except Exception:
                body = (resp.text or "")[:800]
                logger.error(f"[ZIBAL] request non-JSON: {body!r}")
                return PaymentResponse(success=False, error="پاسخ نامعتبر از درگاه زیبال")
            result = data.get("result")
            track_id = str(data.get("trackId", ""))

            if result == 100 and track_id:
                payment_url = f"{base}/start/{track_id}"
                logger.info(f"[ZIBAL{' SANDBOX' if is_sandbox else ''}] Created: trackId={track_id}")
                return PaymentResponse(success=True, authority=track_id, payment_url=payment_url)
            else:
                error_msg = data.get("message", f"result={result}")
                logger.error(f"[ZIBAL] Error: {error_msg}")
                return PaymentResponse(success=False, error=_zibal_humanize_error(str(error_msg)))

    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return PaymentResponse(success=False, error="httpx not installed")
    except Exception as e:
        logger.error(f"[ZIBAL] Exception: {e}")
        return PaymentResponse(success=False, error=_zibal_humanize_error(str(e)))


async def _zibal_verify(track_id: str, amount: int) -> PaymentResponse:
    """Zibal: POST to /v1/verify with trackId."""
    merchant = settings.ZIBAL_MERCHANT
    if not merchant:
        if settings.DEBUG:
            return _mock_verify(track_id, amount)
        return PaymentResponse(success=False, error="ZIBAL_MERCHANT is not configured")

    base = _zibal_base_url()

    try:
        import httpx
        url = f"{base}/v1/verify"

        async with httpx.AsyncClient(timeout=15) as client:
            verify_body: dict = {
                "merchant": merchant,
                "trackId": int(track_id) if track_id.isdigit() else track_id,
            }
            if bool(getattr(settings, "ZIBAL_SANDBOX", False)):
                verify_body["sandbox"] = True
            resp = await client.post(
                url,
                json=verify_body,
            )
            if resp.status_code and resp.status_code >= 400:
                body = (resp.text or "")[:500]
                logger.error(f"[ZIBAL] verify HTTP {resp.status_code}: {body!r}")
                return PaymentResponse(
                    success=False,
                    authority=track_id,
                    error=f"خطای ارتباط با درگاه (HTTP {resp.status_code})",
                )
            try:
                data = resp.json()
            except Exception:
                body = (resp.text or "")[:800]
                logger.error(f"[ZIBAL] verify non-JSON: {body!r}")
                return PaymentResponse(
                    success=False, authority=track_id, error="پاسخ نامعتبر از verify زیبال"
                )
            result = data.get("result")
            order_id = str(data.get("orderId", "") or "").strip()

            def _zibal_amount_match() -> bool:
                try:
                    paid = int(data.get("amount", -1) or -1)
                except (TypeError, ValueError):
                    return False
                return paid == int(amount)

            if result not in (100, 201):
                error_msg = data.get("message", f"result={result}")
                logger.error(f"[ZIBAL] Verify error: {error_msg}")
                return PaymentResponse(success=False, authority=track_id, error=error_msg)

            if not _zibal_amount_match():
                logger.error(
                    f"[ZIBAL] amount mismatch: expected_rial={amount} response={data.get('amount')!r}"
                )
                return PaymentResponse(
                    success=False,
                    authority=track_id,
                    error="عدم تطابق مبلغ تایید با سفارش",
                )

            ref_number = str(data.get("refNumber", "") or "").strip()
            if not ref_number:
                logger.error(f"[ZIBAL] missing refNumber in verify response: keys={list(data.keys())}")
                return PaymentResponse(
                    success=False, authority=track_id, error="refNumber خالی در پاسخ تایید"
                )
            logger.info(
                f"[ZIBAL] Verified: trackId={track_id}, refNumber={ref_number[:16]}… orderId={order_id!r}"
            )
            return PaymentResponse(success=True, authority=track_id, ref_id=ref_number)

    except Exception as e:
        logger.error(f"[ZIBAL] Verify exception: {e}")
        return PaymentResponse(success=False, authority=track_id, error=str(e))


# ─── Zarinpal (REST v4) ──────────────────────────────────────────

def _zarinpal_api_base() -> str:
    if getattr(settings, "ZARINPAL_SANDBOX", False):
        return "https://sandbox.zarinpal.com"
    return "https://api.zarinpal.com"


def _zarinpal_pay_base() -> str:
    if getattr(settings, "ZARINPAL_SANDBOX", False):
        return "https://sandbox.zarinpal.com"
    return "https://www.zarinpal.com"


async def _zarinpal_create(request: PaymentRequest) -> PaymentResponse:
    """Zarinpal v4: POST pg/v4/payment/request.json → authority → StartPay."""
    merchant = getattr(settings, "ZARINPAL_MERCHANT_ID", "") or ""
    if not merchant:
        logger.warning("ZARINPAL_MERCHANT_ID not set")
        return PaymentResponse(
            success=False,
            error="درگاه زرین‌پال روی سرور تنظیم نشده؛ متغیر ZARINPAL_MERCHANT_ID را در محیط اجرا قرار دهید.",
        )

    api_base = _zarinpal_api_base()
    pay_base = _zarinpal_pay_base()

    try:
        import httpx
        url = f"{api_base}/pg/v4/payment/request.json"
        payload: dict = {
            "merchant_id": merchant,
            "amount": request.amount,
            "callback_url": request.callback_url,
            "description": request.description[:255] if request.description else "پرداخت",
        }
        if request.mobile:
            payload["metadata"] = {"mobile": request.mobile}

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, json=payload)
            body = resp.json()
            errors = body.get("errors") or []
            if errors:
                err = errors[0] if isinstance(errors, list) and errors else str(errors)
                logger.error(f"[ZARINPAL] request errors: {err}")
                return PaymentResponse(success=False, error=str(err))
            data = body.get("data") or {}
            code = data.get("code")
            authority = str(data.get("authority", "") or "").strip()
            if code == 100 and authority:
                payment_url = f"{pay_base}/pg/StartPay/{authority}"
                logger.info(f"[ZARINPAL] Created: authority={authority[:24]}…")
                return PaymentResponse(success=True, authority=authority, payment_url=payment_url)
            msg = data.get("message", f"code={code}")
            logger.error(f"[ZARINPAL] Error: {msg}")
            return PaymentResponse(success=False, error=str(msg))

    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return PaymentResponse(success=False, error="httpx not installed")
    except Exception as e:
        logger.error(f"[ZARINPAL] Exception: {e}")
        return PaymentResponse(success=False, error=str(e))


async def _zarinpal_verify(authority: str, amount: int) -> PaymentResponse:
    """Zarinpal v4: POST pg/v4/payment/verify.json."""
    merchant = getattr(settings, "ZARINPAL_MERCHANT_ID", "") or ""
    if not merchant:
        if settings.DEBUG:
            return _mock_verify(authority, amount)
        return PaymentResponse(success=False, error="ZARINPAL_MERCHANT_ID is not configured")

    api_base = _zarinpal_api_base()
    url = f"{api_base}/pg/v4/payment/verify.json"

    try:
        import httpx
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                url,
                json={
                    "merchant_id": merchant,
                    "amount": amount,
                    "authority": authority,
                },
            )
            body = resp.json()
            data = body.get("data") or {}
            code = data.get("code")
            errors = body.get("errors") or []

            if code == 100:
                ref_raw = data.get("ref_id")
                ref_id = str(ref_raw) if ref_raw is not None else ""
                logger.info(f"[ZARINPAL] Verified: authority={authority[:20]}… ref_id={ref_id}")
                return PaymentResponse(success=True, authority=authority, ref_id=ref_id)
            if code == 101:
                ref_raw = data.get("ref_id")
                if ref_raw is not None:
                    ref_id = str(ref_raw)
                    logger.info(f"[ZARINPAL] Already verified (101): ref_id={ref_id}")
                    return PaymentResponse(success=True, authority=authority, ref_id=ref_id)

            if errors:
                err = errors[0] if isinstance(errors, list) and errors else str(errors)
                logger.error(f"[ZARINPAL] Verify error: {err}")
                return PaymentResponse(success=False, authority=authority, error=str(err))
            msg = data.get("message", f"code={code}")
            logger.error(f"[ZARINPAL] Verify failed: {msg}")
            return PaymentResponse(success=False, authority=authority, error=str(msg))

    except Exception as e:
        logger.error(f"[ZARINPAL] Verify exception: {e}")
        return PaymentResponse(success=False, authority=authority, error=str(e))
