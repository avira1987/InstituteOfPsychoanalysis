"""SMS Gateway - Pluggable SMS sending.

Providers:
  - "log"           → development (logs only)
  - "mellipayamak"  → Melli Payamak (OTP via rest.payamak-panel.com SendOtp; notify via console or REST)
  - "kavenegar"     → Kavenegar API

OTP login uses Melipayamak **SendOtp** (webservice-Otp.pdf):
  POST https://rest.payamak-panel.com/api/SendSMS/SendOtp
  Fields: username, password, from, to, code (integer — panel inserts default template text).

General SMS (official SDK: github.com/Melipayamak/melipayamak-python — melipayamak/sms/rest.py):
  POST https://rest.payamak-panel.com/api/SendSMS/SendSMS
  Form: username, password, to, from, text, isFlash

Configure via .env:
  SMS_PROVIDER=mellipayamak
  SMS_USERNAME=نام_کاربری_پنل
  # رمز: یا SMS_PASSWORD (رمز وب‌سرویس کلاسیک) یا طبق راهنمای پنل همان APIKey را در SMS_API_KEY بگذارید
  # (پنل: «مقدار فوق را به‌جای رمز عبور در پارامتر Password به متدها ارسال نمایید» → ما همان را در فیلد password می‌فرستیم).
  SMS_PASSWORD=                    # اختیاری اگر SMS_API_KEY پر باشد
  SMS_API_KEY=...                  # اغلب = همان APIKey به‌عنوان password برای rest.payamak-panel.com
  SMS_LINE_NUMBER=3000xxxx
  # اگر فقط APIKey دارید و SMS_USERNAME خالی است: مسیر جایگزین POST .../api/send/simple/{token} (node-melipayamak)
"""

import asyncio
import logging
import re
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# کنسول REST ملی‌پیامک — توکن API در مسیر URL قرار می‌گیرد (مستند غیررسمی اما هم‌راستا با node-melipayamak)
_MELLI_CONSOLE_API_BASE = "https://console.melipayamak.com/api"


def _mellipayamak_password_for_rest() -> str:
    """پارامتر password برای rest.payamak-panel.com: رمز وب‌سرویس یا همان APIKey طبق راهنمای پنل."""
    p = (settings.SMS_PASSWORD or "").strip()
    return p if p else (settings.SMS_API_KEY or "").strip()


_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
_AR_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


def normalize_ir_mobile(phone: str) -> str:
    """Normalize Iranian mobile to 09xxxxxxxxx (11 ASCII digits).

    Accepts Persian/Arabic digits, spaces, +98 / 0098 / 98… prefixes.
    """
    p = (phone or "").strip()
    p = p.translate(_FA_DIGITS).translate(_AR_DIGITS)
    p = re.sub(r"\s+", "", p)
    p = p.replace("-", "")
    if p.startswith("+98"):
        p = "0" + p[3:]
    elif p.startswith("0098"):
        p = "0" + p[4:]
    elif p.startswith("98") and len(p) >= 12:
        p = "0" + p[2:]
    return p


def _normalize_ir_mobile(phone: str) -> str:
    """Backward-compatible alias for SMS helpers."""
    return normalize_ir_mobile(phone)


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
        f"کد ورود دانشجویی شما به پورتال انستیتو روانکاوی تهران: {code}\n"
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


def _payamak_rest_send_sms_response_ok(data: object) -> bool:
    """پاسخ JSON متد SendSMS روی rest (مشابه سایر متدهای REST پنل)."""
    if not isinstance(data, dict):
        return False
    if _payamak_send_otp_response_ok(data):
        return True
    val = data.get("Value")
    if val is not None and str(val).strip().isdigit() and int(str(val).strip()) > 0:
        return True
    if str(data.get("RetStatus", "")).strip() in ("2", "200"):
        return True
    return False


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
    """Send login OTP: SendOtp روی rest وقتی username + (رمز یا APIKey به‌عنوان password)؛ وگرنه مسیر console/send/simple."""
    provider = (settings.SMS_PROVIDER or "log").lower()

    if provider == "log":
        return _send_log(phone, f"otp_digits={len(code or '')}")

    if provider == "mellipayamak":
        username = (settings.SMS_USERNAME or "").strip()
        api_key = (settings.SMS_API_KEY or "").strip()
        webservice_password = _mellipayamak_password_for_rest()
        if username and webservice_password:
            return await _send_mellipayamak_otp_rest(phone, code, username, webservice_password)
        if api_key:
            return await _send_mellipayamak(phone, _otp_fallback_message_fa(code))
        logger.warning(
            "Melipayamak OTP: need SMS_USERNAME+(SMS_PASSWORD|SMS_API_KEY) or SMS_API_KEY for console",
        )
        return {
            "success": False,
            "provider": "mellipayamak",
            "error": "تنظیمات پیامک ملی‌پیامک ناقص است (نام کاربری/رمز یا APIKey).",
        }

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
    """کنسول ملی‌پیامک فعلاً خط را در پاسخ‌های استاندارد API عمومی با توکن-در-مسیر ارائه نمی‌کند؛ خط را در .env بگذارید."""
    return ""


async def _send_mellipayamak_rest_classic(phone: str, message: str) -> dict:
    """ارسال متن کامل مطابق نمونهٔ رسمی melipayamak/sms/rest.py (SendSMS)."""
    import httpx

    username = (settings.SMS_USERNAME or "").strip()
    password = _mellipayamak_password_for_rest()
    if not username or not password:
        return {
            "success": False,
            "provider": "mellipayamak_rest",
            "error": "برای REST ملی‌پیامک SMS_USERNAME و (SMS_PASSWORD یا SMS_API_KEY به‌عنوان password) لازم است.",
        }

    to = _normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", to):
        return {
            "success": False,
            "provider": "mellipayamak_rest",
            "error": "شماره گیرنده باید به صورت 09xxxxxxxxx باشد.",
        }

    line = (settings.SMS_LINE_NUMBER or "").strip()
    if not line:
        line = await _try_fetch_line_rest_payamak(username, password)
    if not line:
        return {
            "success": False,
            "provider": "mellipayamak_rest",
            "error": "SMS_LINE_NUMBER خالی است و GetUserNumbers خطی برنگرداند.",
        }

    url = "https://rest.payamak-panel.com/api/SendSMS/SendSMS"
    form = {
        "username": username,
        "password": password,
        "to": to,
        "from": line,
        "text": message or "",
        "isFlash": "false",
    }

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, data=form)
            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            if resp.status_code == 200 and isinstance(data, dict) and _payamak_rest_send_sms_response_ok(data):
                logger.info(
                    "[SMS-MELLIPAYAMAK-REST] SendSMS ok to=%s RetStatus=%s",
                    to,
                    data.get("RetStatus"),
                )
                return {"success": True, "provider": "mellipayamak_rest", "response": data}

            err = data if isinstance(data, dict) else resp.text
            logger.error(
                "Melipayamak REST SendSMS failed: HTTP %s body=%s",
                resp.status_code,
                err,
            )
            return {
                "success": False,
                "provider": "mellipayamak_rest",
                "error": str(err) if err else f"HTTP {resp.status_code}",
            }
    except ImportError:
        return {"success": False, "provider": "mellipayamak_rest", "error": "httpx not installed"}
    except Exception as e:
        logger.error("Melipayamak REST SendSMS exception: %s", e)
        return {"success": False, "provider": "mellipayamak_rest", "error": str(e)}


def _mellipayamak_console_response_ok(data: object) -> bool:
    """پاسخ send/simple کنسول: موفقیت = وجود recId / recIds (مطابق README node-melipayamak)."""
    if not isinstance(data, dict):
        return False
    rid = data.get("recId")
    if rid is not None and str(rid).strip() != "":
        return True
    rids = data.get("recIds")
    if isinstance(rids, list) and len(rids) > 0:
        return True
    return False


async def _send_mellipayamak(phone: str, message: str) -> dict:
    """Melli Payamak: ابتدا REST پنل (username + password یا APIKey به‌جای password)، سپس در صورت نیاز console/send/simple/{token}."""
    username = (settings.SMS_USERNAME or "").strip()
    api_key = (settings.SMS_API_KEY or "").strip()
    rest_pw = _mellipayamak_password_for_rest()
    rest_result: dict | None = None

    if username and rest_pw:
        rest_result = await _send_mellipayamak_rest_classic(phone, message)
        if rest_result.get("success"):
            return rest_result
        logger.warning(
            "[SMS-MELLIPAYAMAK] REST SendSMS failed (%s); trying console API",
            rest_result.get("error"),
        )

    if not api_key:
        if rest_result is not None:
            return rest_result
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

        # توکن در مسیر؛ UUID استاندارد کاراکتر امن مسیر است (بدون نیاز به encode)
        token_seg = api_key.strip()
        url = f"{_MELLI_CONSOLE_API_BASE}/send/simple/{token_seg}"

        payload: dict = {"to": to, "text": message}
        if line:
            payload["from"] = line

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Anistito-SMS/1.0 (melipayamak console)",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload, headers=headers)

            try:
                data = resp.json()
            except Exception:
                data = {"raw": resp.text}

            if resp.status_code == 200 and _mellipayamak_console_response_ok(data):
                logger.info(
                    "[SMS-MELLIPAYAMAK] sent to=%s ok recId=%s",
                    to,
                    (data.get("recId") if isinstance(data, dict) else None),
                )
                return {"success": True, "provider": "mellipayamak", "response": data}

            err_detail = data if isinstance(data, dict) else resp.text
            if isinstance(data, dict):
                for key in ("status", "message", "error", "errors", "title", "detail"):
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
            console_err = {"success": False, "provider": "mellipayamak", "error": error_text}
            if rest_result is not None:
                return {
                    "success": False,
                    "provider": "mellipayamak",
                    "error": (
                        f"Console: {error_text}; REST: {rest_result.get('error')}"
                    ),
                }
            return console_err

    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return {"success": False, "provider": "mellipayamak", "error": "httpx not installed"}
    except Exception as e:
        err = str(e).strip() or repr(e) or type(e).__name__
        logger.error("Mellipayamak exception: %s", err)
        hint = ""
        if not line:
            hint = " Set SMS_LINE_NUMBER in .env from your Melipayamak panel."
        out = {
            "success": False,
            "provider": "mellipayamak",
            "error": f"{err}{hint}",
        }
        if rest_result is not None:
            out["error"] = f"Console: {out['error']}; REST: {rest_result.get('error')}"
        return out


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
