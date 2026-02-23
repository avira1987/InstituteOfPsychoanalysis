"""SMS Gateway - Pluggable SMS sending.

Providers:
  - "log"           → development (logs only)
  - "mellipayamak"  → Melli Payamak REST API (console.melipayamak.com)
  - "kavenegar"     → Kavenegar API

Configure via .env:
  SMS_PROVIDER=mellipayamak
  SMS_API_KEY=your-api-token
"""

import logging
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


async def send_sms(phone: str, message: str) -> dict:
    """Send SMS via the configured provider."""
    provider = settings.SMS_PROVIDER or "log"

    if provider == "mellipayamak":
        return await _send_mellipayamak(phone, message)
    elif provider == "kavenegar":
        return await _send_kavenegar(phone, message)
    else:
        return _send_log(phone, message)


def _send_log(phone: str, message: str) -> dict:
    logger.info(f"[SMS-LOG] To: {phone} | Message: {message}")
    return {"success": True, "provider": "log", "phone": phone}


async def _send_mellipayamak(phone: str, message: str) -> dict:
    """Melli Payamak REST Console API.

    Uses the token-based REST API at console.melipayamak.com.
    SMS_API_KEY should be the API token from the console.
    """
    api_key = settings.SMS_API_KEY
    if not api_key:
        logger.warning("SMS_API_KEY not set for mellipayamak, falling back to log")
        return _send_log(phone, message)

    try:
        import httpx
        url = "https://console.melipayamak.com/api/send/simple"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(url, json={
                "from": "",
                "to": phone,
                "text": message,
            }, headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            })

            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"[SMS-MELLIPAYAMAK] Sent to {phone}, recId={data}")
                return {"success": True, "provider": "mellipayamak", "response": data}
            else:
                error_text = resp.text
                logger.error(f"[SMS-MELLIPAYAMAK] Error {resp.status_code}: {error_text}")
                return {"success": False, "provider": "mellipayamak", "error": error_text}

    except ImportError:
        logger.error("httpx not installed. Run: pip install httpx")
        return {"success": False, "provider": "mellipayamak", "error": "httpx not installed"}
    except Exception as e:
        logger.error(f"[SMS-MELLIPAYAMAK] Exception: {e}")
        return {"success": False, "provider": "mellipayamak", "error": str(e)}


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
