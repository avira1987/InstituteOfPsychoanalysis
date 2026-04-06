"""SMS Gateway - Pluggable SMS sending.

Providers:
  - "log"           → development (logs only)
  - "mellipayamak"  → Melli Payamak (OTP via rest.payamak-panel.com SendOtp; notify via console or REST)
  - "kavenegar"     → Kavenegar API

OTP login uses Melipayamak **SendOtp** (webservice-Otp.pdf):
  POST https://rest.payamak-panel.com/api/SendSMS/SendOtp
  Fields: username, password, from, to, code (integer — panel inserts default template text).

Configure via .env:
  SMS_PROVIDER=mellipayamak
  SMS_USERNAME=panel_username
  SMS_PASSWORD=webservice_password   # often different from console Bearer token
  SMS_API_KEY=...                    # used as SMS_PASSWORD if SMS_PASSWORD empty
  SMS_LINE_NUMBER=3000xxxx
"""

import asyncio
import logging
import re
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _normalize_ir_mobile(phone: str) -> str:
    """Normalize Iranian mobile to 09xxxxxxxxx (11 digits)."""
    p = re.sub(r"\s+", "", (phone or "").strip())
    if p.startswith("+98"):
        p = "0" + p[3:]
    elif p.startswith("98") and len(p) >= 12:
        p = "0" + p[2:]
    return p


async def send_sms(phone: str, message: str) -> dict:
    """Send SMS via the configured provider."""
    provider = (settings.SMS_PROVIDER or "log").lower()

    if provider == "mellipayamak":
        return await _send_mellipayamak(phone, message)
    if provider == "kavenegar":
        return await _send_kavenegar(phone, message)
    else:
        return _send_log(phone, message)


def _otp_fallback_message_fa(code: str) -> str:
    """Full SMS body when not using SendOtp (Kavenegar / console fallback)."""
    return (
        f"کد ورود دانشجویی شما به پورتال انیستیتو روانکاوی تهران: {code}\n"
        f"این کد تا ۲ دقیقه معتبر است."
    )


def _payamak_send_otp_response_ok(data: object) -> bool:
    """rest.payamak-panel.com SendOtp JSON: RetStatus==1 or StrRetStatus Ok."""
    if not isinstance(data, dict):
        return False
    rs = data.get("RetStatus")
    if rs is None:
        rs = data.get("retStatus")
    if rs == 1 or str(rs) == "1":
        return True
    s = str(data.get("StrRetStatus", data.get("strRetStatus", ""))).strip().lower()
    return s == "ok"


async def _try_fetch_line_rest_payamak(username: str, password: str) -> str:
    """GetUserNumbers on rest.payamak-panel.com (same credentials as SendOtp)."""
    import httpx

    url = "https://rest.payamak-panel.com/api/SendSMS/GetUserNumbers"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                data={"username": username, "password": password},
            )
            if resp.status_code != 200:
                return ""
            data = resp.json()
            line = _extract_first_sender_line(data)
            if line:
                logger.info("[SMS-MELLIPAYAMAK-OTP] sender line from GetUserNumbers (suffix ...%s)", line[-4:])
            return line or ""
    except Exception as e:
        logger.debug("GetUserNumbers: %s", e)
    return ""


async def _send_mellipayamak_otp_rest(phone: str, code: str, username: str, password: str) -> dict:
    """Official OTP endpoint: only numeric code; message template is set by Melipayamak."""
    import httpx

    to = _normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", to):
        return {
            "success": False,
            "provider": "mellipayamak_otp",
            "error": "Invalid recipient mobile (09xxxxxxxxx).",
        }

    try:
        code_int = int(code)
    except (TypeError, ValueError):
        return {"success": False, "provider": "mellipayamak_otp", "error": "Invalid OTP code."}

    line = (settings.SMS_LINE_NUMBER or "").strip()
    if not line:
        line = await _try_fetch_line_rest_payamak(username, password)

    if not line:
        return {
            "success": False,
            "provider": "mellipayamak_otp",
            "error": "SMS_LINE_NUMBER missing; set sender line in .env or ensure GetUserNumbers returns a line.",
        }

    url = "https://rest.payamak-panel.com/api/SendSMS/SendOtp"
    form = {
        "username": username,
        "password": password,
        "to": to,
        "code": str(code_int),
        "from": line,
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, data=form)
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            if resp.status_code == 200 and isinstance(data, dict) and _payamak_send_otp_response_ok(data):
                logger.info(
                    "[SMS-MELLIPAYAMAK-OTP] SendOtp ok to=%s RetStatus=%s",
                    to,
                    data.get("RetStatus"),
                )
                return {"success": True, "provider": "mellipayamak_otp", "response": data}

            err = data if isinstance(data, dict) else resp.text
            logger.error(
                "Melipayamak SendOtp failed: HTTP %s RetStatus=%s",
                resp.status_code,
                (data.get("RetStatus") if isinstance(data, dict) else None),
            )
            logger.debug("SendOtp body: %s", err)
            return {
                "success": False,
                "provider": "mellipayamak_otp",
                "error": str(err) if err else f"HTTP {resp.status_code}",
            }
    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return {"success": False, "provider": "mellipayamak_otp", "error": "httpx not installed"}
    except Exception as e:
        logger.error("Melipayamak SendOtp exception: %s", e)
        return {"success": False, "provider": "mellipayamak_otp", "error": str(e)}


async def send_otp_sms(phone: str, code: str) -> dict:
    """Send login OTP: Melipayamak SendOtp (REST) when username+password; else generic SMS text."""
    provider = (settings.SMS_PROVIDER or "log").lower()

    if provider == "log":
        return _send_log(phone, f"otp_digits={len(code or '')}")

    if provider == "mellipayamak":
        username = (settings.SMS_USERNAME or "").strip()
        password = (settings.SMS_PASSWORD or settings.SMS_API_KEY or "").strip()
        if username and password:
            return await _send_mellipayamak_otp_rest(phone, code, username, password)
        logger.warning(
            "Melipayamak OTP: SMS_USERNAME or password missing; using console simple SMS (set SMS_USERNAME + SMS_PASSWORD for SendOtp)",
        )
        return await _send_mellipayamak(phone, _otp_fallback_message_fa(code))

    if provider == "kavenegar":
        return await _send_kavenegar(phone, _otp_fallback_message_fa(code))

    return _send_log(phone, f"otp_digits={len(code or '')}")


def _send_log(phone: str, message: str) -> dict:
    # Do not log full message body (often Persian SMS text) to keep Docker logs ASCII-only.
    logger.info("[SMS-LOG] to=%s payload_chars=%s", phone, len(message or ""))
    return {"success": True, "provider": "log", "phone": phone}


def _extract_first_sender_line(obj: object) -> str | None:
    """از پاسخ JSON لیست خطوط، اولین شماره خط شبیه خط پیامک را برمی‌دارد."""
    if isinstance(obj, str):
        s = re.sub(r"\s+", "", obj.strip())
        if re.fullmatch(r"\d{10,14}", s):
            return s
        return None
    if isinstance(obj, dict):
        for v in obj.values():
            r = _extract_first_sender_line(v)
            if r:
                return r
    if isinstance(obj, list):
        for item in obj:
            r = _extract_first_sender_line(item)
            if r:
                return r
    return None


async def _try_fetch_mellipayamak_line(api_key: str) -> str:
    """اگر SMS_LINE_NUMBER خالی باشد، با Bearer سعی می‌کند خط ارسال را از API کنسول بگیرد."""
    import httpx

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    candidates = (
        "https://console.melipayamak.com/api/SharedService/GetUserLines",
        "https://console.melipayamak.com/api/Line/GetLines",
        "https://console.melipayamak.com/api/line/list",
        "https://console.melipayamak.com/api/User/GetLines",
        "https://console.melipayamak.com/api/numbers",
    )

    async def _one(client: httpx.AsyncClient, url: str) -> str:
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                return ""
            data = resp.json()
            line = _extract_first_sender_line(data)
            if line:
                logger.info("[SMS-MELLIPAYAMAK] Resolved sender line via console API (suffix ...%s)", line[-4:])
            return line or ""
        except Exception as e:
            logger.debug("[SMS-MELLIPAYAMAK] Line probe %s: %s", url, e)
            return ""

    timeout = httpx.Timeout(6.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        results = await asyncio.gather(*[_one(client, u) for u in candidates])
    for line in results:
        if line:
            return line
    return ""


def _mellipayamak_body_indicates_success(data: object) -> bool:
    """Parse console REST JSON — recId/recIds یعنی قطعاً OK؛ وگرنه در غیاب فیلدهای خطا، ۲۰۰ را OK می‌گیریم."""
    if not isinstance(data, dict):
        return True
    rid = data.get("recId")
    rids = data.get("recIds")
    if rid is not None and str(rid).strip() != "":
        return True
    if isinstance(rids, list) and len(rids) > 0:
        return True
    for k in ("message", "error", "errors"):
        v = data.get(k)
        if v is None:
            continue
        s = str(v).strip().lower()
        if s and s not in ("ok", "success", "true", "0"):
            return False
    st = data.get("status")
    if isinstance(st, str) and len(st) > 2 and not st.strip().isdigit():
        return False
    return True


async def _send_mellipayamak(phone: str, message: str) -> dict:
    """Melli Payamak REST Console API.

    Uses the token-based REST API at console.melipayamak.com.
    SMS_API_KEY should be the API token from the console.
    """
    api_key = settings.SMS_API_KEY
    if not api_key:
        logger.warning("SMS_API_KEY not set for mellipayamak, falling back to log")
        return _send_log(phone, message)

    to = _normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", to):
        return {
            "success": False,
            "provider": "mellipayamak",
            "error": "شماره گیرنده باید به صورت 09xxxxxxxxx باشد.",
        }

    line = (settings.SMS_LINE_NUMBER or "").strip()
    if not line:
        line = await _try_fetch_mellipayamak_line(api_key)

    try:
        import httpx
        url = "https://console.melipayamak.com/api/send/simple"

        payload: dict = {"to": to, "text": message}
        if line:
            payload["from"] = line

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json=payload, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            })

            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            if resp.status_code == 200 and _mellipayamak_body_indicates_success(data):
                logger.info(
                    "[SMS-MELLIPAYAMAK] sent to=%s ok response_keys=%s",
                    to,
                    list(data.keys()) if isinstance(data, dict) else type(data).__name__,
                )
                return {"success": True, "provider": "mellipayamak", "response": data}

            err_detail = data if isinstance(data, dict) else resp.text
            if isinstance(data, dict):
                for key in ("message", "error", "errors", "status"):
                    if key in data and data[key] not in (None, "", 0, "0"):
                        err_detail = data[key]
                        break
            error_text = str(err_detail) if err_detail else (resp.text or f"HTTP {resp.status_code}")
            if not str(error_text).strip():
                error_text = f"Invalid SMS gateway response (HTTP {resp.status_code})"
            if not line:
                error_text = (
                    f"{error_text} — Set SMS_LINE_NUMBER in .env from your Melipayamak panel."
                )
            logger.error(
                "Mellipayamak send failed: HTTP %s (see debug log for provider message)",
                resp.status_code,
            )
            logger.debug("Mellipayamak error detail: %s", error_text)
            return {"success": False, "provider": "mellipayamak", "error": error_text}

    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return {"success": False, "provider": "mellipayamak", "error": "httpx not installed"}
    except Exception as e:
        err = str(e).strip() or repr(e) or type(e).__name__
        logger.error("Mellipayamak exception: %s", err)
        hint = ""
        if not line:
            hint = " Set SMS_LINE_NUMBER in .env from your Melipayamak panel."
        return {
            "success": False,
            "provider": "mellipayamak",
            "error": f"{err}{hint}",
        }


async def _send_kavenegar(phone: str, message: str) -> dict:
    """Kavenegar API."""
    api_key = settings.SMS_API_KEY
    if not api_key:
        logger.warning("SMS_API_KEY not set for kavenegar, falling back to log")
        return _send_log(phone, message)

    try:
        import httpx
        url = f"https://api.kavenegar.com/v1/{api_key}/sms/send.json"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, data={
                "receptor": phone,
                "message": message,
            })
            data = resp.json()
            if resp.status_code == 200:
                logger.info(f"[SMS-KAVENEGAR] Sent to {phone}")
                return {"success": True, "provider": "kavenegar", "response": data}
            else:
                logger.error(f"[SMS-KAVENEGAR] Error: {data}")
                return {"success": False, "provider": "kavenegar", "error": str(data)}
    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return {"success": False, "provider": "kavenegar", "error": "httpx not installed"}
    except Exception as e:
        logger.error(f"[SMS-KAVENEGAR] Exception: {e}")
        return {"success": False, "provider": "kavenegar", "error": str(e)}
