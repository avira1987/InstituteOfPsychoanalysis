"""HTTP client for Alocom panel API (pnlapi.alocom.co).

Paths default to values typical of v4.x docs; override via Settings if your tenant differs.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

import httpx

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AlocomAPIError(Exception):
    """Raised when Alocom returns an error or an unexpected payload."""

    def __init__(self, message: str, status_code: int | None = None, body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.body = body


def _extract_token(data: dict) -> Optional[str]:
    if not isinstance(data, dict):
        return None
    for key in ("token", "access_token", "accessToken"):
        v = data.get(key)
        if isinstance(v, str) and v:
            return v
    inner = data.get("data")
    if isinstance(inner, dict):
        for key in ("token", "access_token", "accessToken"):
            v = inner.get(key)
            if isinstance(v, str) and v:
                return v
    return None


def _unwrap_data(obj: Any) -> dict:
    if isinstance(obj, dict) and isinstance(obj.get("data"), dict):
        return obj["data"]
    if isinstance(obj, dict):
        return obj
    return {}


def _extract_event_id_and_link(data: dict) -> tuple[Optional[str], Optional[str]]:
    """Best-effort parse after create/update event."""
    d = _unwrap_data(data)
    event = d.get("event")
    if isinstance(event, dict):
        eid = event.get("id")
        link = event.get("alocom_link") or event.get("alocomLink")
        if eid is not None:
            return str(eid), link if isinstance(link, str) else None
    eid = d.get("id") or d.get("event_id") or d.get("eventId")
    link = d.get("alocom_link") or d.get("alocomLink")
    if eid is not None:
        return str(eid), link if isinstance(link, str) else None
    return None, None


def _extract_register_link(data: dict) -> Optional[str]:
    d = _unwrap_data(data)
    for key in ("eventLink", "event_link", "link", "url"):
        v = d.get(key)
        if isinstance(v, str) and v.startswith("http"):
            return v
    return None


class AlocomClient:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._token: Optional[str] = None
        self._lock = asyncio.Lock()

    def _base(self) -> str:
        return (self.settings.ALOCOM_API_BASE or "").rstrip("/")

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        async with self._lock:
            if self._token:
                return self._token
            await self._login_unlocked(client)
            if not self._token:
                raise AlocomAPIError("Alocom login did not return a token")
            return self._token

    async def _login_unlocked(self, client: httpx.AsyncClient) -> None:
        url = f"{self._base()}{self.settings.ALOCOM_PATH_LOGIN}"
        body = {
            "username": self.settings.ALOCOM_USERNAME,
            "password": self.settings.ALOCOM_PASSWORD,
        }
        r = await client.post(url, json=body)
        if r.status_code >= 400:
            raise AlocomAPIError(
                f"Alocom login failed: HTTP {r.status_code}",
                status_code=r.status_code,
                body=_safe_json(r),
            )
        data = r.json() if r.content else {}
        tok = _extract_token(data if isinstance(data, dict) else {})
        if not tok:
            raise AlocomAPIError("Alocom login response missing token", body=data)
        self._token = tok
        logger.info("Alocom login OK (token cached in process)")

    async def invalidate_token(self) -> None:
        async with self._lock:
            self._token = None

    async def create_event(
        self,
        *,
        title: str,
        agent_service_id: int,
        slug: str,
        start_by_admin: int = 1,
        status: int = 1,
        duration_time: Optional[int] = None,
        users: Optional[list[dict[str, Any]]] = None,
        local_record_available: bool = False,
        guest_access: Optional[bool] = None,
    ) -> dict:
        """POST create event; returns parsed JSON dict."""
        payload: dict[str, Any] = {
            "title": title,
            "agent_service_id": agent_service_id,
            "start_by_admin": int(start_by_admin),
            "status": int(status),
            "slug": slug,
            "local_record_available": bool(local_record_available),
        }
        if duration_time is not None:
            payload["duration_time"] = int(duration_time)
        if users is not None:
            payload["users"] = users
        if guest_access is not None:
            payload["guest_access"] = bool(guest_access)

        async with httpx.AsyncClient(timeout=60.0) as client:
            return await self._post_json(client, self.settings.ALOCOM_PATH_CREATE_EVENT, payload)

    async def create_agent_user(
        self,
        *,
        name: str,
        surname: str,
        username: str,
        status: int = 1,
        cellphone: Optional[str] = None,
        email: Optional[str] = None,
    ) -> dict:
        body: dict[str, Any] = {
            "name": name or "User",
            "surname": surname or "-",
            "username": username,
            "status": int(status),
        }
        if cellphone:
            body["cellphone"] = cellphone
        if email:
            body["email"] = email
        async with httpx.AsyncClient(timeout=60.0) as client:
            return await self._post_json(client, self.settings.ALOCOM_PATH_CREATE_USER, body)

    async def register_user_in_event(
        self,
        event_id: str,
        *,
        name: str,
        surname: str,
        username: str,
        role: str,
    ) -> dict:
        path = self.settings.ALOCOM_PATH_REGISTER_IN_EVENT.format(event_id=event_id)
        body = {
            "name": name or "User",
            "surname": surname or "-",
            "username": username,
            "role": role,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            return await self._post_json(client, path, body)

    async def _post_json(self, client: httpx.AsyncClient, path: str, json_body: dict) -> dict:
        url = f"{self._base()}{path}"
        headers = {}
        attempt = 0
        while attempt < 2:
            attempt += 1
            token = await self._ensure_token(client)
            headers["Authorization"] = f"Bearer {token}"
            r = await client.post(url, json=json_body, headers=headers)
            if r.status_code == 401 and attempt < 2:
                await self.invalidate_token()
                continue
            if r.status_code >= 400:
                raise AlocomAPIError(
                    f"Alocom POST {path} failed: HTTP {r.status_code}",
                    status_code=r.status_code,
                    body=_safe_json(r),
                )
            out = r.json() if r.content else {}
            return out if isinstance(out, dict) else {"_raw": out}
        raise AlocomAPIError("Alocom request retry exhausted")


def _safe_json(r: httpx.Response) -> Any:
    try:
        return r.json()
    except Exception:
        return (r.text or "")[:2000]


def extract_agent_user_id(create_user_response: dict) -> Optional[int]:
    d = _unwrap_data(create_user_response)
    for key in ("id", "userId", "user_id", "agent_user_id"):
        v = d.get(key)
        if isinstance(v, int):
            return v
        if isinstance(v, str) and v.isdigit():
            return int(v)
    msg = create_user_response.get("message") if isinstance(create_user_response, dict) else None
    if isinstance(msg, str) and "ایجاد" in msg:
        # user might already exist — some APIs return username only
        pass
    return None
