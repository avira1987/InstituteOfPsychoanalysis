"""SMS Gateway - Pluggable SMS sending.

Official samples: https://github.com/Melipayamak/melipayamak-python

Providers:
  - "log"           → development (no gateway call)
  - "mellipayamak"  → Melli Payamak REST / console fallback

OTP: SendOtp — POST https://rest.payamak-panel.com/api/SendSMS/SendOtp

متن آزاد (نیاز به SMS_LINE_NUMBER): SendSMS — POST .../SendSMS

خط خدماتی اشتراکی / پترن (SendByBaseNumber2 معادل REST):
  مستند: https://www.melipayamak.com/api/sendbybasenumber2/
  POST https://rest.payamak-panel.com/api/SendSMS/BaseServiceNumber
  پارامتر text = مقادیر متغیرهای پترن به‌ترتیب با جداکننده ; (semicolon)

Configure (`app.config.ENV_FILE_PATH`, یا ANISTITO_ENV_FILE):

  SMS_PROVIDER=mellipayamak
  SMS_USERNAME=...
  SMS_PASSWORD= یا SMS_API_KEY به‌عنوان password
  SMS_LINE_NUMBER=...   برای SendSMS / SendOtp
  SMS_OTP_PATTERN_BODY_ID=449667 اختیاری؛ ارسال کد ورود با پترن خط خدماتی قبل از SendSMS/SendOtp
  نگاشت قالب‌های اعلان → bodyId: metadata/sms_template_pattern_map.json
  هر جا send_sms(..., template_key=..., context=...) صدا زده شود، در صورت وجود نگاشت همان BaseServiceNumber استفاده می‌شود.
"""

import re

import httpx

from app.config import get_settings

settings = get_settings()

# یک اتصال نگه‌دارندهٔ HTTP به rest.payamak-panel.com — هر درخواست OTP قبلاً TLS جدید می‌گرفت.
_PAYAMAK_REST_CLIENT: httpx.AsyncClient | None = None


def _mellipayamak_rest_async_client() -> httpx.AsyncClient:
    global _PAYAMAK_REST_CLIENT
    if _PAYAMAK_REST_CLIENT is None:
        _PAYAMAK_REST_CLIENT = httpx.AsyncClient(
            base_url="https://rest.payamak-panel.com",
            timeout=httpx.Timeout(25.0, connect=12.0),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=24),
        )
    return _PAYAMAK_REST_CLIENT


# کنسول REST ملی‌پیامک — توکن API در مسیر URL قرار می‌گیرد (مستند غیررسمی اما هم‌راستا با node-melipayamak)
_MELLI_CONSOLE_API_BASE = "https://console.melipayamak.com/api"


def _mellipayamak_password_for_rest() -> str:
    """پارامتر password برای rest.payamak-panel.com: رمز وب‌سرویس یا همان APIKey طبق راهنمای پنل."""
    p = (settings.SMS_PASSWORD or "").strip().replace("\r", "")
    return p if p else (settings.SMS_API_KEY or "").strip().replace("\r", "")


def _sms_sender_line() -> str:
    """شماره خط ارسال؛ CRLF یا کاراکترهای مخفی .env روی ویندوز را حذف می‌کند."""
    return (settings.SMS_LINE_NUMBER or "").strip().replace("\r", "").strip()


def _sms_rest_username() -> str:
    return (settings.SMS_USERNAME or "").strip().replace("\r", "").strip()


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


async def _attach_popup_mirror(
    phone: str,
    result: dict,
    *,
    message: str = "",
    kind: str = "notification",
    template_key: str | None = None,
    context: dict | None = None,
) -> dict:
    """پس از ارسال واقعی، متن را در outbox بگذار تا پاپ‌آپ و middleware همان درخواست آن را ببینند."""
    if not result.get("success"):
        return result
    from app.services.notification_service import resolve_sms_message_body
    from app.services.sms_simulation_service import entry_dict, mirror_sms_for_popup

    display = (message or "").strip()
    tk = (template_key or "").strip() or None
    if tk:
        display = resolve_sms_message_body(tk, dict(context or {}), message_override=display or None)
    if not display:
        display = message or f"پیامک [{tk or 'sms'}]"
    sid = await mirror_sms_for_popup(
        phone,
        display,
        kind=kind,
        template_key=tk,
    )
    if sid:
        import uuid

        sms_id = sid or uuid.uuid4().hex
        result["simulated_sms_id"] = sid
        result["simulated_sms"] = entry_dict(
            sms_id=sms_id,
            phone=_normalize_ir_mobile(phone),
            message=display,
            kind=kind,
            template_key=tk,
        )
    return result


async def send_sms(
    phone: str,
    message: str,
    *,
    template_key: str | None = None,
    context: dict | None = None,
) -> dict:
    """ارسال پیامک؛ اگر برای template_key در sms_template_pattern_map.json نگاشت باشد، ابتدا BaseServiceNumber."""
    provider = (settings.SMS_PROVIDER or "log").lower()
    tk = (template_key or "").strip() or None
    sms_kind = "notification" if tk else "free_text"

    if provider == "mellipayamak" and tk:
        from app.services.sms_template_pattern_map import resolve_sms_pattern_for_template

        resolved = resolve_sms_pattern_for_template(str(tk).strip(), dict(context or {}))
        if resolved:
            bid, ptext = resolved
            return await send_sms_pattern(
                phone,
                bid,
                ptext,
                template_key=tk,
                context=context,
            )

    if provider == "mellipayamak":
        res = await _send_mellipayamak(phone, message)
        return await _attach_popup_mirror(
            phone,
            res,
            message=message,
            kind=sms_kind,
            template_key=tk,
            context=context,
        )
    return await _simulate_sms_async(phone, message, kind=sms_kind, template_key=tk)


async def send_sms_pattern(
    phone: str,
    body_id: int,
    pattern_text: str,
    *,
    template_key: str | None = None,
    context: dict | None = None,
    popup_kind: str = "pattern",
    popup_message: str | None = None,
) -> dict:
    """ارسال با خط خدماتی اشتراکی — REST BaseServiceNumber (معادل SendByBaseNumber2).

    pattern_text = مقادیر {0}؛{1}؛… مطابق پترن پنل، با نقطه‌ویرگول لاتین.
    """
    provider = (settings.SMS_PROVIDER or "log").lower()
    if provider != "mellipayamak":
        composed = f"[pattern bodyId={body_id}] {pattern_text}"
        return await _simulate_sms_async(phone, composed, kind=popup_kind or "pattern")
    if body_id <= 0:
        return {"success": False, "provider": "mellipayamak_pattern", "error": "bodyId نامعتبر است."}
    res = await _send_mellipayamak_rest_base_service_number(phone, pattern_text or "", body_id)
    display = popup_message or pattern_text or f"پترن bodyId={body_id}"
    return await _attach_popup_mirror(
        phone,
        res,
        message=display,
        kind=popup_kind or "pattern",
        template_key=template_key,
        context=context,
    )


def _otp_login_sms_body_fa(code: str) -> str:
    """متن یکسان پیامک کد ورود (SendSMS / کنسول / پترن باید با همین معنا در پنل ثبت شود)."""
    c = str(code or "").strip()
    return f"کد ورود:{c} انستیتو روانکاوری تهران"


def _otp_fallback_message_fa(code: str) -> str:
    """همان متن ورود برای fallback کنسول."""
    return _otp_login_sms_body_fa(code)


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
    try:
        client = _mellipayamak_rest_async_client()
        resp = await client.post(
            "/api/SendSMS/GetUserNumbers",
            data={"username": username, "password": password},
        )
        if resp.status_code != 200:
            return ""
        data = resp.json()
        line = _extract_first_sender_line(data)
        return line or ""
    except Exception:
        pass
    return ""


async def _send_mellipayamak_otp_rest(phone: str, code: str, username: str, password: str) -> dict:
    """Official OTP endpoint: only numeric code; message template is set by Melipayamak."""
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

    line = _sms_sender_line()
    if not line:
        line = await _try_fetch_line_rest_payamak(username, password)

    if not line:
        return {
            "success": False,
            "provider": "mellipayamak_otp",
            "error": "SMS_LINE_NUMBER missing; set sender line in .env or ensure GetUserNumbers returns a line.",
        }

    form = {
        "username": username,
        "password": password,
        "to": to,
        "code": str(code_int),
        "from": line,
    }

    try:
        client = _mellipayamak_rest_async_client()
        resp = await client.post("/api/SendSMS/SendOtp", data=form)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

        if resp.status_code == 200 and isinstance(data, dict) and _payamak_send_otp_response_ok(data):
            return {"success": True, "provider": "mellipayamak_otp", "response": data}

        err = data if isinstance(data, dict) else resp.text
        return {
            "success": False,
            "provider": "mellipayamak_otp",
            "error": str(err) if err else f"HTTP {resp.status_code}",
        }
    except ImportError:
        return {"success": False, "provider": "mellipayamak_otp", "error": "httpx not installed"}
    except Exception as e:
        return {"success": False, "provider": "mellipayamak_otp", "error": str(e)}


async def send_otp_sms(phone: str, code: str) -> dict:
    """کد ورود: اول پترن خط خدماتی (SMS_OTP_PATTERN_BODY_ID)، سپس SendSMS با متن کامل، سپس SendOtp؛ وگرنه کنسول."""
    provider = (settings.SMS_PROVIDER or "log").lower()

    if provider == "log":
        body = _otp_login_sms_body_fa(code)
        to = _normalize_ir_mobile(phone)
        return {"success": True, "provider": "log", "phone": to, "simulated_message": body}

    if provider == "mellipayamak":
        username = _sms_rest_username()
        api_key = (settings.SMS_API_KEY or "").strip()
        webservice_password = _mellipayamak_password_for_rest()
        body = _otp_login_sms_body_fa(code)
        try:
            otp_pat_id = int(getattr(settings, "SMS_OTP_PATTERN_BODY_ID", 0) or 0)
        except (TypeError, ValueError):
            otp_pat_id = 0
        if username and webservice_password:
            if otp_pat_id > 0:
                pat_res = await send_sms_pattern(
                    phone,
                    otp_pat_id,
                    str(code or "").strip(),
                    popup_kind="otp",
                    popup_message=body,
                )
                if pat_res.get("success"):
                    return pat_res
            classic = await _send_mellipayamak_rest_classic(phone, body)
            if classic.get("success"):
                return await _attach_popup_mirror(phone, classic, message=body, kind="otp")
            otp_res = await _send_mellipayamak_otp_rest(phone, code, username, webservice_password)
            return await _attach_popup_mirror(phone, otp_res, message=body, kind="otp")
        if api_key:
            res = await _send_mellipayamak(phone, body)
            return await _attach_popup_mirror(phone, res, message=body, kind="otp")
        return {
            "success": False,
            "provider": "mellipayamak",
            "error": "تنظیمات پیامک ملی‌پیامک ناقص است (نام کاربری/رمز یا APIKey).",
        }

    body = _otp_login_sms_body_fa(code)
    to = _normalize_ir_mobile(phone)
    return {"success": True, "provider": "log", "phone": to, "simulated_message": body}


async def _simulate_sms_async(
    phone: str,
    message: str,
    *,
    kind: str,
    template_key: str | None = None,
) -> dict:
    """حالت log: پاسخ موفق + در صورت فعال بودن، ذخیره در outbox برای پاپ‌آپ تست."""
    import uuid

    from app.services.sms_simulation_service import (
        entry_dict,
        record_simulated_sms,
        simulation_recording_enabled,
    )

    to = _normalize_ir_mobile(phone)
    msg = message or ""
    base: dict = {"success": True, "provider": "log", "phone": to, "simulated_message": msg}
    if not simulation_recording_enabled():
        return base

    kind_norm = (kind or "free_text").strip()
    sid = await record_simulated_sms(to, msg, kind=kind_norm, template_key=template_key)
    sms_id = sid or uuid.uuid4().hex
    if sid:
        base["simulated_sms_id"] = sid
    base["simulated_sms"] = entry_dict(
        sms_id=sms_id,
        phone=to,
        message=msg,
        kind=kind_norm,
        template_key=template_key,
    )
    return base


def _send_log(phone: str, message: str) -> dict:
    return {"success": True, "provider": "log", "phone": _normalize_ir_mobile(phone)}


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
    username = _sms_rest_username()
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

    line = _sms_sender_line()
    if not line:
        line = await _try_fetch_line_rest_payamak(username, password)
    if not line:
        return {
            "success": False,
            "provider": "mellipayamak_rest",
            "error": "SMS_LINE_NUMBER خالی است و GetUserNumbers خطی برنگرداند.",
        }

    form = {
        "username": username,
        "password": password,
        "to": to,
        "from": line,
        "text": message or "",
        "isFlash": "false",
    }

    try:
        client = _mellipayamak_rest_async_client()
        resp = await client.post("/api/SendSMS/SendSMS", data=form)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

        if resp.status_code == 200 and isinstance(data, dict) and _payamak_rest_send_sms_response_ok(data):
            return {"success": True, "provider": "mellipayamak_rest", "response": data}

        err = data if isinstance(data, dict) else resp.text
        return {
            "success": False,
            "provider": "mellipayamak_rest",
            "error": str(err) if err else f"HTTP {resp.status_code}",
        }
    except ImportError:
        return {"success": False, "provider": "mellipayamak_rest", "error": "httpx not installed"}
    except Exception as e:
        return {"success": False, "provider": "mellipayamak_rest", "error": str(e)}


async def _send_mellipayamak_rest_base_service_number(phone: str, message: str, body_id: int) -> dict:
    """ارسال پترن خط خدماتی اشتراکی — REST BaseServiceNumber (معادل SendByBaseNumber2 در مستند SOAP).

    مستند: https://www.melipayamak.com/api/sendbybasenumber2/
    endpoint مطابق نموهٔ curl رسمی همان صفحه.
    """
    username = _sms_rest_username()
    password = _mellipayamak_password_for_rest()
    if not username or not password:
        return {
            "success": False,
            "provider": "mellipayamak_pattern",
            "error": "برای BaseServiceNumber SMS_USERNAME و (SMS_PASSWORD یا SMS_API_KEY) لازم است.",
        }

    to = _normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", to):
        return {
            "success": False,
            "provider": "mellipayamak_pattern",
            "error": "شماره گیرنده باید به صورت 09xxxxxxxxx باشد.",
        }

    if body_id <= 0:
        return {
            "success": False,
            "provider": "mellipayamak_pattern",
            "error": "bodyId نامعتبر است.",
        }

    form = {
        "username": username,
        "password": password,
        "to": to,
        "text": message or "",
        "bodyId": str(body_id),
    }

    try:
        client = _mellipayamak_rest_async_client()
        resp = await client.post("/api/SendSMS/BaseServiceNumber", data=form)
        try:
            data = resp.json()
        except Exception:
            data = {"raw": resp.text}

        if resp.status_code == 200 and isinstance(data, dict) and _payamak_rest_send_sms_response_ok(data):
            return {"success": True, "provider": "mellipayamak_pattern", "response": data}

        err = data if isinstance(data, dict) else resp.text
        return {
            "success": False,
            "provider": "mellipayamak_pattern",
            "error": str(err) if err else f"HTTP {resp.status_code}",
        }
    except ImportError:
        return {"success": False, "provider": "mellipayamak_pattern", "error": "httpx not installed"}
    except Exception as e:
        return {"success": False, "provider": "mellipayamak_pattern", "error": str(e)}


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
    """Melli Payamak: REST SendSMS (متن آزاد) در صورت داشتن خط؛ وگرنه API کنسول."""
    username = _sms_rest_username()
    api_key = (settings.SMS_API_KEY or "").strip()
    rest_pw = _mellipayamak_password_for_rest()
    rest_result: dict | None = None

    if username and rest_pw:
        rest_result = await _send_mellipayamak_rest_classic(phone, message)
        if rest_result.get("success"):
            return rest_result

    if not api_key:
        if rest_result is not None:
            return rest_result
        return _send_log(phone, message)

    to = _normalize_ir_mobile(phone)
    if not re.fullmatch(r"09\d{9}", to):
        return {
            "success": False,
            "provider": "mellipayamak",
            "error": "شماره گیرنده باید به صورت 09xxxxxxxxx باشد.",
        }

    line = _sms_sender_line()
    if not line:
        line = await _try_fetch_mellipayamak_line(api_key)

    def _rest_failures_suffix() -> str:
        parts: list[str] = []
        if rest_result:
            parts.append(f"REST(SendSMS): {rest_result.get('error')}")
        return "; ".join(parts)

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
            sfx = _rest_failures_suffix()
            console_err = {
                "success": False,
                "provider": "mellipayamak",
                "error": f"Console: {error_text}; {sfx}" if sfx else error_text,
            }
            return console_err

    except ImportError:
        return {"success": False, "provider": "mellipayamak", "error": "httpx not installed"}
    except Exception as e:
        err = str(e).strip() or repr(e) or type(e).__name__
        hint = ""
        if not line:
            hint = " Set SMS_LINE_NUMBER in .env from your Melipayamak panel."
        sfx = _rest_failures_suffix()
        out = {
            "success": False,
            "provider": "mellipayamak",
            "error": f"{err}{hint}",
        }
        if sfx:
            out["error"] = f"Console: {out['error']}; {sfx}"
        return out
