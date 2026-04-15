"""Payment Gateway - Pluggable payment processing.

Providers:
  - "mock"   → development (always succeeds)
  - "saman"  → Saman (SEP) via sep.shaparak.ir (amounts in Rials)
  - "zibal"  → Zibal via gateway.zibal.ir

Configure via .env (never commit real secrets):
  PAYMENT_PROVIDER=saman
  SEP_TERMINAL_ID=<terminal_id>
  SEP_PASSWORD=<optional per merchant doc>
  PAYMENT_CALLBACK_URL=https://yourdomain.com/api/payment/callback

  # or for Zibal:
  PAYMENT_PROVIDER=zibal
  ZIBAL_MERCHANT=your_merchant_id
"""

import uuid
import logging
from typing import Optional
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class PaymentRequest:
    def __init__(self, amount: int, description: str, callback_url: str = "",
                 student_id: Optional[str] = None, reference_id: Optional[str] = None,
                 mobile: Optional[str] = None):
        self.amount = amount
        self.description = description
        self.callback_url = callback_url or settings.PAYMENT_CALLBACK_URL
        self.student_id = student_id
        self.reference_id = reference_id
        self.mobile = mobile


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

async def create_payment(request: PaymentRequest) -> PaymentResponse:
    provider = settings.PAYMENT_PROVIDER or "mock"
    if provider == "saman":
        return await _saman_create(request)
    elif provider == "zibal":
        return await _zibal_create(request)
    else:
        return _mock_create(request)


async def verify_payment(authority: str, amount: int) -> PaymentResponse:
    provider = settings.PAYMENT_PROVIDER or "mock"
    if provider == "saman":
        return await _saman_verify(authority, amount)
    elif provider == "zibal":
        return await _zibal_verify(authority, amount)
    else:
        return _mock_verify(authority, amount)


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

async def _saman_create(request: PaymentRequest) -> PaymentResponse:
    """Saman SEP: GetToken then redirect to payment page.

    Flow:
    1. POST to /OnlinePG/SendToken → get Token
    2. Redirect user to /OnlinePG/OnlinePG with Token
    3. User pays, gets redirected to callback_url
    4. Verify via /verifyTxnRandomSessionkey/ipg/VerifyTransaction
    """
    terminal_id = settings.SEP_TERMINAL_ID
    if not terminal_id:
        logger.warning("SEP_TERMINAL_ID not set, falling back to mock")
        return _mock_create(request)

    try:
        import httpx
        token_url = "https://sep.shaparak.ir/OnlinePG/SendToken"

        payload = {
            "Action": "Token",
            "TerminalId": terminal_id,
            "Amount": request.amount,
            "ResNum": request.reference_id or str(uuid.uuid4().hex[:16]),
            "RedirectUrl": request.callback_url,
            "CellNumber": request.mobile or "",
        }
        pw = (getattr(settings, "SEP_PASSWORD", None) or "").strip()
        if pw:
            payload["Password"] = pw

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(token_url, json=payload)
            data = resp.json()

            status = data.get("status")
            token = data.get("token", "")

            if status == 1 and token:
                payment_url = f"https://sep.shaparak.ir/OnlinePG/OnlinePG?Token={token}"
                logger.info(f"[SEP] Token obtained: {token[:20]}...")
                return PaymentResponse(success=True, authority=token, payment_url=payment_url)
            else:
                error_msg = data.get("errorDesc", f"status={status}")
                logger.error(f"[SEP] Token error: {error_msg}")
                return PaymentResponse(success=False, error=error_msg)

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
        return _mock_verify(ref_num, amount)

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
    """Return Zibal API base URL (sandbox or production)."""
    if getattr(settings, "ZIBAL_SANDBOX", True):
        return "https://sandbox.zibal.ir"
    return "https://gateway.zibal.ir"


async def _zibal_create(request: PaymentRequest) -> PaymentResponse:
    """Zibal: POST to /v1/request → get trackId → redirect."""
    merchant = settings.ZIBAL_MERCHANT
    if not merchant:
        logger.warning("ZIBAL_MERCHANT not set, falling back to mock")
        return _mock_create(request)

    base = _zibal_base_url()
    is_sandbox = "sandbox" in base

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
            data = resp.json()
            result = data.get("result")
            track_id = str(data.get("trackId", ""))

            if result == 100 and track_id:
                payment_url = f"{base}/start/{track_id}"
                logger.info(f"[ZIBAL{' SANDBOX' if is_sandbox else ''}] Created: trackId={track_id}")
                return PaymentResponse(success=True, authority=track_id, payment_url=payment_url)
            else:
                error_msg = data.get("message", f"result={result}")
                logger.error(f"[ZIBAL] Error: {error_msg}")
                return PaymentResponse(success=False, error=error_msg)

    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return PaymentResponse(success=False, error="httpx not installed")
    except Exception as e:
        logger.error(f"[ZIBAL] Exception: {e}")
        return PaymentResponse(success=False, error=str(e))


async def _zibal_verify(track_id: str, amount: int) -> PaymentResponse:
    """Zibal: POST to /v1/verify with trackId."""
    merchant = settings.ZIBAL_MERCHANT
    if not merchant:
        return _mock_verify(track_id, amount)

    base = _zibal_base_url()

    try:
        import httpx
        url = f"{base}/v1/verify"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={
                "merchant": merchant,
                "trackId": int(track_id) if track_id.isdigit() else track_id,
            })
            data = resp.json()
            result = data.get("result")

            if result == 100:
                ref_number = str(data.get("refNumber", ""))
                logger.info(f"[ZIBAL] Verified: trackId={track_id}, refNumber={ref_number}")
                return PaymentResponse(success=True, authority=track_id, ref_id=ref_number)
            else:
                error_msg = data.get("message", f"result={result}")
                logger.error(f"[ZIBAL] Verify error: {error_msg}")
                return PaymentResponse(success=False, authority=track_id, error=error_msg)

    except Exception as e:
        logger.error(f"[ZIBAL] Verify exception: {e}")
        return PaymentResponse(success=False, authority=track_id, error=str(e))
